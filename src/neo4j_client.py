"""
Neo4j client module for graph database connectivity.

This module provides configuration and connection management for Neo4j,
including schema retrieval for validation and tool usage.

This is the single source of truth for Neo4j connectivity - used by both
the general application and the Neo4jContextProvider.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("azureaiapp")


class Neo4jSettings(BaseSettings):
    """
    Neo4j configuration loaded from environment variables.

    All settings use the NEO4J_ prefix for environment variables.
    Example: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

    Attributes:
        uri: Neo4j connection URI
        username: Neo4j username
        password: Neo4j password (SecretStr for security)
        index_name: Default index name for searches
        index_type: Default index type (vector or fulltext)
        vector_dimensions: Dimensions for vector embeddings
    """

    model_config = SettingsConfigDict(
        env_prefix="NEO4J_",
        extra="ignore",
    )

    # Connection settings
    uri: str | None = Field(
        default=None,
        description="Neo4j connection URI (e.g., bolt://localhost:7687)",
    )
    username: str | None = Field(
        default=None,
        description="Neo4j username",
    )
    password: SecretStr | None = Field(
        default=None,
        description="Neo4j password",
    )

    # Index configuration (for context provider)
    index_name: str | None = Field(
        default=None,
        description="Name of the Neo4j index to query",
    )
    index_type: str | None = Field(
        default=None,
        description="Type of index: 'vector' or 'fulltext'",
    )
    vector_dimensions: int | None = Field(
        default=None,
        description="Dimensions of embedding vectors (e.g., 1536 for ada-002)",
    )

    # Context provider mode
    mode: str | None = Field(
        default=None,
        description="Search mode: 'basic' or 'graph_enriched'",
    )

    @property
    def is_configured(self) -> bool:
        """Check if all required Neo4j connection settings are provided."""
        return all([self.uri, self.username, self.password])

    def get_password(self) -> str | None:
        """Safely retrieve the password value."""
        if self.password is None:
            return None
        return self.password.get_secret_value()


# Backwards compatibility alias
Neo4jConfig = Neo4jSettings


class GraphSchema(BaseModel):
    """
    Represents the schema of a Neo4j graph database.

    Attributes:
        node_labels: List of node labels in the database
        relationship_types: List of relationship types in the database
        node_properties: Dictionary mapping node labels to their properties
        relationship_properties: Dictionary mapping relationship types to their properties
    """

    node_labels: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)
    node_properties: dict[str, list[str]] = Field(default_factory=dict)
    relationship_properties: dict[str, list[str]] = Field(default_factory=dict)

    def summary(self) -> str:
        """Return a human-readable summary of the schema."""
        return (
            f"Schema: {len(self.node_labels)} node labels, "
            f"{len(self.relationship_types)} relationship types"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert schema to dictionary representation."""
        return {
            "node_labels": self.node_labels,
            "relationship_types": self.relationship_types,
            "node_properties": self.node_properties,
            "relationship_properties": self.relationship_properties,
        }


class Neo4jClient:
    """
    Async Neo4j client for managing database connections and queries.

    Use as an async context manager to ensure proper resource cleanup:

        async with Neo4jClient(settings) as client:
            schema = await client.get_schema()

    Can also be used by the Neo4jContextProvider for shared connectivity.
    """

    def __init__(self, settings: Neo4jSettings) -> None:
        """
        Initialize the Neo4j client.

        Args:
            settings: Neo4j settings with connection details.

        Raises:
            ValueError: If required configuration is missing.
        """
        if not settings.is_configured:
            raise ValueError(
                "Neo4j configuration incomplete. "
                "Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD"
            )
        self._settings = settings
        self._driver: AsyncDriver | None = None

    async def __aenter__(self) -> Neo4jClient:
        """Enter async context and establish connection."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close connection."""
        await self.close()

    async def connect(self) -> None:
        """
        Establish connection to Neo4j database.

        Raises:
            ConnectionError: If connection fails.
        """
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.uri,
                auth=(self._settings.username, self._settings.get_password()),
            )
            # Verify connectivity
            await self._driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self._settings.uri}")
        except AuthError as e:
            logger.error(f"Neo4j authentication failed: {e}")
            raise ConnectionError(f"Neo4j authentication failed: {e}") from e
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {e}")
            raise ConnectionError(f"Neo4j service unavailable: {e}") from e
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Failed to connect to Neo4j: {e}") from e

    async def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    @property
    def driver(self) -> AsyncDriver:
        """Get the Neo4j driver, raising if not connected."""
        if not self._driver:
            raise RuntimeError("Neo4j client not connected. Use as async context manager.")
        return self._driver

    async def get_schema(self) -> GraphSchema:
        """
        Retrieve the graph database schema.

        Returns:
            GraphSchema containing node labels, relationship types, and properties.

        Raises:
            RuntimeError: If not connected to the database.
        """
        schema = GraphSchema()

        async with self.driver.session() as session:
            # Get node labels
            result = await session.run("CALL db.labels()")
            records = await result.data()
            schema.node_labels = [record["label"] for record in records]

            # Get relationship types
            result = await session.run("CALL db.relationshipTypes()")
            records = await result.data()
            schema.relationship_types = [record["relationshipType"] for record in records]

            # Get node properties per label
            for label in schema.node_labels:
                result = await session.run(
                    f"MATCH (n:`{label}`) "
                    "WITH n LIMIT 100 "
                    "UNWIND keys(n) AS key "
                    "RETURN DISTINCT key"
                )
                records = await result.data()
                schema.node_properties[label] = [record["key"] for record in records]

            # Get relationship properties per type
            for rel_type in schema.relationship_types:
                result = await session.run(
                    f"MATCH ()-[r:`{rel_type}`]->() "
                    "WITH r LIMIT 100 "
                    "UNWIND keys(r) AS key "
                    "RETURN DISTINCT key"
                )
                records = await result.data()
                schema.relationship_properties[rel_type] = [record["key"] for record in records]

        logger.info(f"Retrieved schema: {schema.summary()}")
        return schema

    async def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string.
            parameters: Optional query parameters.

        Returns:
            List of result records as dictionaries.
        """
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            return await result.data()


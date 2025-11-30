"""
Neo4j utility functions for API endpoints.

Provides entity listing and relationship queries for the REST API.
These are API-specific queries that don't belong in the core Neo4jClient.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j_client import Neo4jClient


async def list_entities_by_type(
    client: Neo4jClient,
    entity_type: str,
    limit: int = 20,
) -> list[dict[str, str]]:
    """List entities of a specific type.

    Args:
        client: Connected Neo4jClient instance.
        entity_type: The entity label (e.g., Company, Executive, Product).
            Caller is responsible for validating the entity type.
        limit: Maximum number of entities to return.

    Returns:
        List of entities with id and name.
    """
    # Use coalesce to fallback to elementId if e.id is not set
    # Filter NULL names to ensure consistent sorting (Cypher best practice)
    query = f"""
    MATCH (e:{entity_type})
    WHERE e.name IS NOT NULL
    RETURN coalesce(e.id, elementId(e)) AS id, e.name AS name
    ORDER BY e.name
    LIMIT $limit
    """

    async with client.driver.session() as session:
        result = await session.run(query, {"limit": limit})
        data = await result.data()
        return [
            {"id": str(record["id"]), "name": record["name"] or ""}
            for record in data
        ]


async def get_entity_relationships(
    client: Neo4jClient,
    entity_name: str,
    limit: int = 20,
) -> list[dict[str, str]]:
    """Get relationships for an entity by name.

    Args:
        client: Connected Neo4jClient instance.
        entity_name: The entity name to search for (case-insensitive contains).
        limit: Maximum number of relationships to return.

    Returns:
        List of relationships with source, relationship type, and target.
    """
    query = """
    MATCH (source)-[r]->(target)
    WHERE source.name IS NOT NULL
      AND target.name IS NOT NULL
      AND toLower(source.name) CONTAINS toLower($entity_name)
      AND NOT source:Document
      AND NOT source:Chunk
      AND NOT target:Document
      AND NOT target:Chunk
    RETURN source.name AS source,
           type(r) AS relationship,
           target.name AS target,
           [label IN labels(source) WHERE NOT label STARTS WITH '__'][0] AS source_type,
           [label IN labels(target) WHERE NOT label STARTS WITH '__'][0] AS target_type
    LIMIT $limit
    """

    async with client.driver.session() as session:
        result = await session.run(
            query,
            {"entity_name": entity_name, "limit": limit},
        )
        data = await result.data()
        return [
            {
                "source": record["source"],
                "source_type": record["source_type"],
                "relationship": record["relationship"],
                "target": record["target"],
                "target_type": record["target_type"],
            }
            for record in data
        ]

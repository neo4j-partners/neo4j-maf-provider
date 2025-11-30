"""
Vector search module for semantic search over Neo4j graph database.

This module provides semantic search capabilities using Azure AI Foundry embeddings
and Neo4j vector indexes, with graph-aware context retrieval.
"""

from __future__ import annotations

import os

from azure.ai.inference import EmbeddingsClient
from azure.ai.inference.models import EmbeddingInputType
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from logging_config import configure_logging
from neo4j_client import Neo4jClient

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))


class VectorSearchConfig(BaseSettings):
    """
    Configuration for vector search with Azure AI Foundry embeddings.

    Uses the same configuration as the data-pipeline for consistency.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
    )

    # Azure AI Foundry project endpoint
    project_endpoint: str | None = Field(
        default=None,
        validation_alias="AZURE_AI_PROJECT_ENDPOINT",
    )

    # Embedding model deployment name
    embedding_deployment: str = Field(
        default="text-embedding-ada-002",
        validation_alias="AZURE_AI_EMBEDDING_NAME",
    )

    # Neo4j vector index name
    vector_index_name: str = Field(
        default="chunkEmbeddings",
        validation_alias="NEO4J_VECTOR_INDEX_NAME",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def inference_endpoint(self) -> str | None:
        """Get the model inference endpoint from project endpoint."""
        if not self.project_endpoint:
            return None
        # Convert project endpoint to model inference endpoint
        if "/api/projects/" in self.project_endpoint:
            base = self.project_endpoint.split("/api/projects/")[0]
            return f"{base}/models"
        return self.project_endpoint

    @property
    def is_configured(self) -> bool:
        """Check if all required settings are provided."""
        return self.project_endpoint is not None


class SearchResultMetadata(BaseModel):
    """Metadata from graph context for a search result."""

    company: str | None = None
    risks: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    """A single semantic search result with graph context."""

    text: str
    score: float
    metadata: SearchResultMetadata


class SemanticSearchResponse(BaseModel):
    """Response from semantic search endpoint."""

    results: list[SearchResult]
    query: str


class SemanticSearchRequest(BaseModel):
    """Request body for semantic search endpoint."""

    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


# Graph-aware retrieval query that enriches results with company and risk context
RETRIEVAL_QUERY = """
MATCH (node)-[:FROM_DOCUMENT]-(doc:Document)-[:FILED]-(company:Company)
OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
WITH node, score, company, collect(DISTINCT risk.name) as risks
RETURN
    node.text as text,
    score,
    company.name as company,
    risks
ORDER BY score DESC
LIMIT $top_k
"""


class VectorSearchClient:
    """
    Client for performing semantic search with graph-aware context.

    Uses Azure AI Foundry for embeddings and Neo4j vector indexes for search.
    """

    def __init__(
        self,
        config: VectorSearchConfig,
        neo4j_client: Neo4jClient,
    ) -> None:
        """
        Initialize the vector search client.

        Args:
            config: Vector search configuration with embedding settings.
            neo4j_client: Connected Neo4j client for database queries.

        Raises:
            ValueError: If required configuration is missing.
        """
        if not config.is_configured:
            raise ValueError(
                "Vector search configuration incomplete. "
                "Required: AZURE_AI_PROJECT_ENDPOINT"
            )

        self._config = config
        self._neo4j_client = neo4j_client

        # Create embeddings client with Azure CLI credentials
        credential = DefaultAzureCredential()
        self._embeddings_client = EmbeddingsClient(
            endpoint=config.inference_endpoint,
            credential=credential,
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )
        logger.info(f"Embeddings client initialized: {config.inference_endpoint}")

    def get_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector for the given text (for queries).

        Args:
            text: Text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        response = self._embeddings_client.embed(
            input=[text],
            model=self._config.embedding_deployment,
            input_type=EmbeddingInputType.QUERY,
        )
        embedding = response.data[0].embedding
        if isinstance(embedding, list):
            return embedding
        raise ValueError(f"Unexpected embedding type: {type(embedding)}")

    async def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Perform semantic search with graph-aware context retrieval.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of SearchResult objects with text, score, and graph metadata.
        """
        # Generate embedding for the query (sync call, but fast)
        query_embedding = self.get_embedding(query)

        # Execute vector search with graph context
        cypher_query = f"""
        CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
        YIELD node, score
        {RETRIEVAL_QUERY}
        """

        results = await self._neo4j_client.execute_query(
            cypher_query,
            {
                "index_name": self._config.vector_index_name,
                "top_k": top_k,
                "embedding": query_embedding,
            },
        )

        # Convert to SearchResult objects
        search_results = []
        for record in results:
            search_results.append(
                SearchResult(
                    text=record.get("text", ""),
                    score=record.get("score", 0.0),
                    metadata=SearchResultMetadata(
                        company=record.get("company"),
                        risks=record.get("risks", []),
                    ),
                )
            )

        logger.info(f"Semantic search for '{query[:50]}...' returned {len(search_results)} results")
        return search_results

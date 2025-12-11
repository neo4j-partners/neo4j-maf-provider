"""
Neo4j Context Provider for Microsoft Agent Framework.

This package provides a context provider that enhances agent responses
with knowledge graph data from Neo4j using vector, fulltext, or hybrid search
via neo4j-graphrag retrievers.

Usage:
    from neo4j_provider import Neo4jContextProvider, AzureAIEmbedder
    from neo4j_client import Neo4jSettings
    from azure.identity import DefaultAzureCredential

    # Create embedder for vector search
    embedder = AzureAIEmbedder(
        endpoint="https://your-project.models.ai.azure.com",
        credential=DefaultAzureCredential(),
    )

    # Create provider with vector search
    provider = Neo4jContextProvider(
        index_name="chunkEmbeddings",
        index_type="vector",
        embedder=embedder,
    )
"""

from neo4j_client import Neo4jSettings

from .embedder import AzureAIEmbedder
from .fulltext import FulltextRetriever
from .provider import Neo4jContextProvider

# Backwards compatibility alias
Neo4jContextProviderSettings = Neo4jSettings

__all__ = [
    "Neo4jContextProvider",
    "Neo4jContextProviderSettings",  # Alias for backwards compatibility
    "Neo4jSettings",
    "AzureAIEmbedder",
    "FulltextRetriever",
]

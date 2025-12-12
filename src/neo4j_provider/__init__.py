"""
Neo4j Context Provider for Microsoft Agent Framework.

This package provides a context provider that enhances agent responses
with knowledge graph data from Neo4j using vector, fulltext, or hybrid search
via neo4j-graphrag retrievers.

Usage:
    from neo4j_provider import Neo4jContextProvider, AzureAIEmbedder, Neo4jSettings, AzureAISettings
    from azure.identity import DefaultAzureCredential

    # Load settings from environment
    neo4j_settings = Neo4jSettings()
    azure_settings = AzureAISettings()

    # Create embedder for vector search
    embedder = AzureAIEmbedder(
        endpoint=azure_settings.inference_endpoint,
        credential=DefaultAzureCredential(),
        model=azure_settings.embedding_model,
    )

    # Create provider with vector search
    provider = Neo4jContextProvider(
        uri=neo4j_settings.uri,
        username=neo4j_settings.username,
        password=neo4j_settings.get_password(),
        index_name=neo4j_settings.vector_index_name,
        index_type="vector",
        embedder=embedder,
    )
"""

from .embedder import AzureAIEmbedder
from .fulltext import FulltextRetriever
from .provider import Neo4jContextProvider
from .settings import AzureAISettings, Neo4jSettings

__all__ = [
    "Neo4jContextProvider",
    "Neo4jSettings",
    "AzureAISettings",
    "AzureAIEmbedder",
    "FulltextRetriever",
]

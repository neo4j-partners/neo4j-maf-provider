"""
Neo4j Context Provider for Microsoft Agent Framework.

This package provides a context provider that enhances agent responses
with knowledge graph data from Neo4j using vector or fulltext search.

Usage:
    from neo4j_provider import Neo4jContextProvider
    from neo4j_client import Neo4jSettings  # Shared settings

    provider = Neo4jContextProvider(
        index_name="chunkEmbeddings",
        index_type="vector",
        vectorizer=my_vectorizer,
    )
"""

from neo4j_client import Neo4jSettings

from .provider import Neo4jContextProvider, VectorizerProtocol

# Backwards compatibility alias
Neo4jContextProviderSettings = Neo4jSettings

__all__ = [
    "Neo4jContextProvider",
    "Neo4jContextProviderSettings",  # Alias for backwards compatibility
    "Neo4jSettings",
    "VectorizerProtocol",
]

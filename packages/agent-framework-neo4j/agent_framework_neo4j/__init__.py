"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j knowledge graphs using vector,
fulltext, or hybrid search with optional graph enrichment.

Example:
    from agent_framework_neo4j import Neo4jContextProvider, Neo4jSettings

    settings = Neo4jSettings()  # Loads from environment

    provider = Neo4jContextProvider(
        uri=settings.uri,
        username=settings.username,
        password=settings.get_password(),
        index_name="chunkEmbeddings",
        index_type="vector",
        embedder=my_embedder,
    )

    async with provider:
        # Use with Microsoft Agent Framework agent
        pass
"""

from ._embedder import AzureAIEmbedder
from ._fulltext import FulltextRetriever
from ._provider import (
    DEFAULT_CONTEXT_PROMPT,
    ConnectionConfig,
    MemoryConfig,
    Neo4jContextProvider,
    ScopeConfig,
    SearchConfig,
)
from ._settings import AzureAISettings, Neo4jSettings

__version__ = "0.1.0"

__all__ = [
    # Main provider
    "Neo4jContextProvider",
    # Configuration dataclasses
    "SearchConfig",
    "MemoryConfig",
    "ScopeConfig",
    "ConnectionConfig",
    "DEFAULT_CONTEXT_PROMPT",
    # Settings (env var loaders)
    "Neo4jSettings",
    "AzureAISettings",
    # Utilities
    "AzureAIEmbedder",
    "FulltextRetriever",
    "__version__",
]

"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j using vector, fulltext, or hybrid search
via neo4j-graphrag retrievers, with optional graph enrichment.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import MutableSequence, Sequence
from typing import Any, ClassVar, Literal

import neo4j
from agent_framework import ChatMessage, Context, ContextProvider, Role
from neo4j_graphrag.embeddings import Embedder
from neo4j_graphrag.retrievers import (
    VectorRetriever,
    VectorCypherRetriever,
    HybridRetriever,
    HybridCypherRetriever,
)
from neo4j_graphrag.types import RetrieverResult

from neo4j_client import Neo4jSettings
from neo4j_provider.fulltext import FulltextRetriever

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


# Type alias for all supported retrievers
RetrieverType = VectorRetriever | VectorCypherRetriever | HybridRetriever | HybridCypherRetriever | FulltextRetriever


class Neo4jContextProvider(ContextProvider):
    """
    Context provider that retrieves knowledge graph context from Neo4j.

    Uses neo4j-graphrag retrievers for search:
    - VectorRetriever / VectorCypherRetriever for vector search
    - HybridRetriever / HybridCypherRetriever for hybrid (vector + fulltext)
    - FulltextRetriever for fulltext-only search

    Key design principles:
    - NO entity extraction - passes full message text to search
    - Index-driven configuration - works with any Neo4j index
    - Configurable enrichment - users define their own retrieval_query
    - Async wrapping - neo4j-graphrag retrievers are sync, wrapped with asyncio.to_thread()
    """

    DEFAULT_CONTEXT_PROMPT: ClassVar[str] = (
        "## Knowledge Graph Context\n"
        "Use the following information from the knowledge graph to answer the question:"
    )

    def __init__(
        self,
        *,
        # Connection (falls back to environment variables)
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        # Index configuration (required)
        index_name: str | None = None,
        index_type: Literal["vector", "fulltext", "hybrid"] = "vector",
        # For hybrid search - optional second index
        fulltext_index_name: str | None = None,
        # Mode selection
        mode: Literal["basic", "graph_enriched"] = "basic",
        # Search parameters
        top_k: int = 5,
        context_prompt: str | None = None,
        # Retrieval query for graph_enriched mode
        retrieval_query: str | None = None,
        # Embedder for vector/hybrid search (neo4j-graphrag Embedder)
        embedder: Embedder | None = None,
        # Message history (like Azure AI Search's agentic mode)
        message_history_count: int = 10,
        # Fulltext search options
        filter_stop_words: bool | None = None,
    ) -> None:
        """
        Initialize the Neo4j context provider.

        Args:
            uri: Neo4j connection URI. Falls back to NEO4J_URI env var.
            username: Neo4j username. Falls back to NEO4J_USERNAME env var.
            password: Neo4j password. Falls back to NEO4J_PASSWORD env var.
            index_name: Name of the Neo4j index to query. Required.
                For vector/hybrid: the vector index name.
                For fulltext: the fulltext index name.
            index_type: Type of search - "vector", "fulltext", or "hybrid".
            fulltext_index_name: Fulltext index name for hybrid search.
                Required when index_type is "hybrid".
            mode: Search mode - "basic" returns raw results,
                  "graph_enriched" uses retrieval_query for graph traversal.
            top_k: Number of results to retrieve.
            context_prompt: Prompt prepended to context.
            retrieval_query: Cypher query for graph enrichment.
                Required when mode is "graph_enriched".
                Must use `node` and `score` variables from index search.
            embedder: neo4j-graphrag Embedder for vector/hybrid search.
                Required when index_type is "vector" or "hybrid".
            message_history_count: Number of recent messages to use for query.
            filter_stop_words: Filter common stop words from fulltext queries.
                Defaults to True for fulltext indexes, False otherwise.
        """
        # Load settings from environment (single source of truth)
        settings = Neo4jSettings()

        # Build effective settings by merging constructor args with env settings
        self._uri = uri or settings.uri
        self._username = username or settings.username
        self._password = password or settings.get_password()

        # Index configuration
        self._index_name = index_name or settings.index_name
        self._index_type: Literal["vector", "fulltext", "hybrid"] = index_type
        self._fulltext_index_name = fulltext_index_name

        # Validate index_name is provided
        if not self._index_name:
            raise ValueError(
                "index_name is required. Set via constructor or NEO4J_INDEX_NAME env var."
            )

        # Validate hybrid search has fulltext index
        if self._index_type == "hybrid" and not self._fulltext_index_name:
            raise ValueError(
                "fulltext_index_name is required when index_type='hybrid'."
            )

        # Mode and retrieval query
        self._mode: Literal["basic", "graph_enriched"] = mode
        self._retrieval_query = retrieval_query

        # Validate retrieval_query for graph_enriched mode
        if self._mode == "graph_enriched" and retrieval_query is None:
            raise ValueError(
                "retrieval_query is required when mode='graph_enriched'. "
                "Provide a Cypher query that uses `node` and `score` from index search."
            )

        # Search parameters
        self._top_k = top_k
        self._context_prompt = context_prompt or self.DEFAULT_CONTEXT_PROMPT
        self._message_history_count = message_history_count

        # Embedder for vector/hybrid search
        self._embedder = embedder

        # Validate embedder for vector/hybrid search
        if self._index_type in ("vector", "hybrid") and embedder is None:
            raise ValueError(
                f"embedder is required when index_type='{self._index_type}'"
            )

        # Stop word filtering - default to True for fulltext, False otherwise
        if filter_stop_words is None:
            self._filter_stop_words = self._index_type == "fulltext"
        else:
            self._filter_stop_words = filter_stop_words

        # Runtime state
        self._driver: neo4j.Driver | None = None
        self._retriever: RetrieverType | None = None

    def _create_retriever(self) -> RetrieverType:
        """Create the appropriate neo4j-graphrag retriever based on configuration."""
        if self._driver is None:
            raise ValueError("Driver not initialized")

        if self._index_type == "vector":
            if self._mode == "graph_enriched":
                return VectorCypherRetriever(
                    driver=self._driver,
                    index_name=self._index_name,
                    retrieval_query=self._retrieval_query,
                    embedder=self._embedder,
                )
            else:
                return VectorRetriever(
                    driver=self._driver,
                    index_name=self._index_name,
                    embedder=self._embedder,
                )

        elif self._index_type == "hybrid":
            if self._mode == "graph_enriched":
                return HybridCypherRetriever(
                    driver=self._driver,
                    vector_index_name=self._index_name,
                    fulltext_index_name=self._fulltext_index_name,
                    retrieval_query=self._retrieval_query,
                    embedder=self._embedder,
                )
            else:
                return HybridRetriever(
                    driver=self._driver,
                    vector_index_name=self._index_name,
                    fulltext_index_name=self._fulltext_index_name,
                    embedder=self._embedder,
                )

        else:  # fulltext
            return FulltextRetriever(
                driver=self._driver,
                index_name=self._index_name,
                retrieval_query=self._retrieval_query if self._mode == "graph_enriched" else None,
                filter_stop_words=self._filter_stop_words,
            )

    async def __aenter__(self) -> Self:
        """Connect to Neo4j and create retriever."""
        if not all([self._uri, self._username, self._password]):
            raise ValueError(
                "Neo4j connection requires uri, username, and password. "
                "Set via constructor or NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars."
            )

        # Create driver
        self._driver = neo4j.GraphDatabase.driver(
            self._uri,
            auth=(self._username, self._password),
        )

        # Verify connectivity (sync call wrapped for async)
        await asyncio.to_thread(self._driver.verify_connectivity)

        # Create retriever in thread pool because neo4j-graphrag retrievers
        # call _fetch_index_infos() during __init__ which makes DB calls
        self._retriever = await asyncio.to_thread(self._create_retriever)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Close Neo4j connection."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            self._retriever = None

    @property
    def is_connected(self) -> bool:
        """Check if the provider is connected to Neo4j."""
        return self._driver is not None and self._retriever is not None

    def _format_retriever_result(self, result: RetrieverResult) -> list[str]:
        """Format neo4j-graphrag RetrieverResult items as text for context."""
        formatted: list[str] = []

        for item in result.items:
            parts: list[str] = []

            # Include score if present in metadata
            if item.metadata and "score" in item.metadata:
                score = item.metadata["score"]
                if score is not None:
                    parts.append(f"[Score: {score:.3f}]")

            # Include other metadata fields
            if item.metadata:
                for key, value in item.metadata.items():
                    if key == "score" or value is None:
                        continue
                    parts.append(self._format_field(key, value))

            # Include content
            if item.content:
                parts.append(str(item.content))

            if parts:
                formatted.append(" ".join(parts))

        return formatted

    def _format_field(self, key: str, value: Any) -> str:
        """Format a single field value, handling lists and scalars."""
        # Try to treat as list first (duck typing)
        try:
            # Strings are iterable but we want them as scalars
            if value == str(value):
                return f"[{key}: {value}]"
        except (TypeError, ValueError):
            pass

        # Try to iterate and join
        try:
            items = list(value)
            if items:
                return f"[{key}: {', '.join(str(v) for v in items)}]"
            return ""
        except TypeError:
            # Not iterable, treat as scalar
            return f"[{key}: {value}]"

    async def _search(self, query_text: str) -> RetrieverResult:
        """Execute search using the configured retriever."""
        if self._retriever is None:
            raise ValueError("Retriever not initialized")

        # neo4j-graphrag retrievers are sync, wrap with asyncio.to_thread
        return await asyncio.to_thread(
            self._retriever.search,
            query_text=query_text,
            top_k=self._top_k,
        )

    async def invoking(
        self,
        messages: ChatMessage | MutableSequence[ChatMessage],
        **kwargs: Any,
    ) -> Context:
        """
        Called before each LLM invocation to provide context.

        Key design: NO entity extraction. The full message text is passed
        to the index search, which handles relevance ranking.
        """
        # Not connected - return empty context
        if not self.is_connected:
            return Context()

        # Convert to list - try iteration first (MutableSequence), fallback to single item
        try:
            messages_list: list[ChatMessage] = list(messages)  # type: ignore[arg-type]
        except TypeError:
            messages_list = [messages]  # type: ignore[list-item]

        # Filter to USER and ASSISTANT messages with text
        filtered_messages = [
            msg
            for msg in messages_list
            if msg.text and msg.text.strip() and msg.role in [Role.USER, Role.ASSISTANT]
        ]

        if not filtered_messages:
            return Context()

        # Take recent messages (like Azure AI Search's agentic mode)
        recent_messages = filtered_messages[-self._message_history_count :]

        # CRITICAL: Concatenate full message text - NO ENTITY EXTRACTION
        query_text = "\n".join(msg.text for msg in recent_messages if msg.text)

        if not query_text.strip():
            return Context()

        # Perform search using retriever
        result = await self._search(query_text)

        if not result.items:
            return Context()

        # Format as context messages
        context_messages = [ChatMessage(role=Role.USER, text=self._context_prompt)]
        formatted_results = self._format_retriever_result(result)
        for text in formatted_results:
            if text:
                context_messages.append(ChatMessage(role=Role.USER, text=text))

        return Context(messages=context_messages)

    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Called after agent response.

        Stub for future conversation memory implementation.
        """
        pass

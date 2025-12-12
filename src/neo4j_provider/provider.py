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
from neo4j_graphrag.types import RetrieverResult, RetrieverResultItem
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from neo4j_provider.fulltext import FulltextRetriever
from neo4j_provider.settings import Neo4jSettings

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


# Type alias for all supported retrievers
RetrieverType = VectorRetriever | VectorCypherRetriever | HybridRetriever | HybridCypherRetriever | FulltextRetriever

# Type aliases for Literal types
IndexType = Literal["vector", "fulltext", "hybrid"]
SearchMode = Literal["basic", "graph_enriched"]


def _format_cypher_result(record: neo4j.Record) -> RetrieverResultItem:
    """
    Format a neo4j Record from a Cypher retrieval query into a RetrieverResultItem.

    Extracts 'text' as content and all other fields as metadata.
    This provides proper parsing of custom retrieval query results.
    """
    data = dict(record)
    # Extract text content (use 'text' field or first string field)
    content = data.pop("text", None)
    if content is None:
        # Fallback: use first string value found
        for key, value in data.items():
            if isinstance(value, str):
                content = value
                break
    if content is None:
        content = str(record)

    # All remaining fields go to metadata
    return RetrieverResultItem(content=str(content), metadata=data if data else None)


class ProviderConfig(BaseModel):
    """
    Pydantic model for Neo4jContextProvider configuration validation.

    Validates all configuration parameters and their interdependencies.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Connection settings
    uri: str | None = None
    username: str | None = None
    password: str | None = None

    # Index configuration
    index_name: str
    index_type: IndexType = "vector"
    fulltext_index_name: str | None = None

    # Mode and retrieval
    mode: SearchMode = "basic"
    retrieval_query: str | None = None

    # Search parameters
    top_k: int = 5
    context_prompt: str | None = None
    message_history_count: int = 10
    filter_stop_words: bool | None = None

    # Embedder (validated separately due to complex type)
    embedder: Embedder | None = None

    @field_validator("top_k")
    @classmethod
    def top_k_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("top_k must be at least 1")
        return v

    @field_validator("message_history_count")
    @classmethod
    def message_history_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("message_history_count must be at least 1")
        return v

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        """Validate interdependent configuration options."""
        # Hybrid search requires fulltext index
        if self.index_type == "hybrid" and not self.fulltext_index_name:
            raise ValueError(
                "fulltext_index_name is required when index_type='hybrid'"
            )

        # Graph-enriched mode requires retrieval query
        if self.mode == "graph_enriched" and not self.retrieval_query:
            raise ValueError(
                "retrieval_query is required when mode='graph_enriched'. "
                "Provide a Cypher query that uses `node` and `score` from index search."
            )

        # Vector/hybrid search requires embedder
        if self.index_type in ("vector", "hybrid") and self.embedder is None:
            raise ValueError(
                f"embedder is required when index_type='{self.index_type}'"
            )

        return self


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
        index_type: IndexType = "vector",
        # For hybrid search - optional second index
        fulltext_index_name: str | None = None,
        # Mode selection
        mode: SearchMode = "basic",
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

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        # Load settings from environment (single source of truth)
        settings = Neo4jSettings()

        # Build effective settings by merging constructor args with env settings
        effective_uri = uri or settings.uri
        effective_username = username or settings.username
        effective_password = password or settings.get_password()
        effective_index_name = index_name or settings.index_name

        # Validate index_name is provided (before Pydantic validation)
        if not effective_index_name:
            raise ValueError(
                "index_name is required. Set via constructor or NEO4J_INDEX_NAME env var."
            )

        # Use Pydantic model for comprehensive validation
        config = ProviderConfig(
            uri=effective_uri,
            username=effective_username,
            password=effective_password,
            index_name=effective_index_name,
            index_type=index_type,
            fulltext_index_name=fulltext_index_name,
            mode=mode,
            retrieval_query=retrieval_query,
            top_k=top_k,
            context_prompt=context_prompt,
            message_history_count=message_history_count,
            filter_stop_words=filter_stop_words,
            embedder=embedder,
        )

        # Store validated configuration
        self._uri = config.uri
        self._username = config.username
        self._password = config.password
        self._index_name = config.index_name
        self._index_type = config.index_type
        self._fulltext_index_name = config.fulltext_index_name
        self._mode = config.mode
        self._retrieval_query = config.retrieval_query
        self._top_k = config.top_k
        self._context_prompt = config.context_prompt or self.DEFAULT_CONTEXT_PROMPT
        self._message_history_count = config.message_history_count
        self._embedder = config.embedder

        # Stop word filtering - default to True for fulltext, False otherwise
        if config.filter_stop_words is None:
            self._filter_stop_words = self._index_type == "fulltext"
        else:
            self._filter_stop_words = config.filter_stop_words

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
                    result_formatter=_format_cypher_result,
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
                    result_formatter=_format_cypher_result,
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

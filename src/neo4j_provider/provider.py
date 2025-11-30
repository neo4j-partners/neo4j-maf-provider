"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j using vector or fulltext search,
with optional graph enrichment via configurable retrieval queries.
"""

from __future__ import annotations

import re
import sys
from collections.abc import MutableSequence, Sequence
from typing import Any, ClassVar, Final, Literal, Protocol, runtime_checkable

from agent_framework import ChatMessage, Context, ContextProvider, Role

from neo4j_client import Neo4jClient, Neo4jSettings
from neo4j_provider.stop_words import FULLTEXT_STOP_WORDS

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@runtime_checkable
class VectorizerProtocol(Protocol):
    """Protocol for vectorizer objects that can embed text.

    Compatible with redisvl.utils.vectorize.BaseVectorizer, allowing reuse
    of the same vectorizer across Redis and Neo4j providers.

    Both methods should be implemented for full compatibility with redisvl.
    The Neo4jContextProvider only uses aembed(), but external code may
    expect the sync embed() method.
    """

    async def aembed(self, text: str) -> list[float]:
        """Asynchronously embed text into a vector."""
        ...

    def embed(self, text: str) -> list[float]:
        """Synchronously embed text into a vector."""
        ...


# Default retrieval query - just returns the search results
DEFAULT_RETRIEVAL_QUERY: Final[str] = """
RETURN node.text AS text, score
ORDER BY score DESC
"""


class Neo4jContextProvider(ContextProvider):
    """
    Context provider that retrieves knowledge graph context from Neo4j.

    Follows the Azure AI Search and Redis provider patterns:
    - index_name: Which index to query
    - index_type: Type of index (vector or fulltext)
    - mode: basic (raw results) or graph_enriched (with retrieval_query)
    - retrieval_query: Custom Cypher for graph context enrichment

    Key design principles:
    - NO entity extraction - passes full message text to search
    - Index-driven configuration - works with any Neo4j index
    - Configurable enrichment - users define their own retrieval_query

    Uses the shared Neo4jClient for database connectivity.
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
        index_type: Literal["vector", "fulltext"] = "vector",
        # Mode selection
        mode: Literal["basic", "graph_enriched"] = "basic",
        # Search parameters
        top_k: int = 5,
        context_prompt: str | None = None,
        # Retrieval query for graph_enriched mode
        retrieval_query: str | None = None,
        # Vector search - vectorizer object (like Redis provider)
        vectorizer: VectorizerProtocol | None = None,
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
            index_type: Type of index - "vector" or "fulltext".
            mode: Search mode - "basic" returns raw results,
                  "graph_enriched" uses retrieval_query.
            top_k: Number of results to retrieve.
            context_prompt: Prompt prepended to context.
            retrieval_query: Cypher query for graph enrichment.
                Required when mode is "graph_enriched".
                Must use `node` and `score` variables from index search.
            vectorizer: Vectorizer object with aembed() method.
                Required when index_type is "vector".
            message_history_count: Number of recent messages to use for query.
            filter_stop_words: Filter common stop words from fulltext queries.
                Defaults to True for fulltext indexes, False for vector indexes.
                Improves fulltext search by extracting keywords from questions.
        """
        # Load settings from environment (single source of truth)
        settings = Neo4jSettings()

        # Build effective settings by merging constructor args with env settings
        effective_uri = uri or settings.uri
        effective_username = username or settings.username
        effective_password = password or settings.get_password()

        # Index configuration
        self._index_name = index_name or settings.index_name
        self._index_type: Literal["vector", "fulltext"] = (
            index_type or settings.index_type or "vector"
        )

        # Validate index_name is provided
        if not self._index_name:
            raise ValueError(
                "index_name is required. Set via constructor or NEO4J_INDEX_NAME env var."
            )

        # Mode and retrieval query (mode can come from settings)
        effective_mode = mode
        if effective_mode == "basic" and settings.mode in ("basic", "graph_enriched"):
            effective_mode = settings.mode  # type: ignore[assignment]
        self._mode: Literal["basic", "graph_enriched"] = effective_mode
        self._retrieval_query = retrieval_query or DEFAULT_RETRIEVAL_QUERY

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

        # Vectorizer
        self._vectorizer = vectorizer

        # Validate vectorizer for vector search
        if self._index_type == "vector" and vectorizer is None:
            raise ValueError("vectorizer is required when index_type='vector'")

        # Stop word filtering - default to True for fulltext, False for vector
        if filter_stop_words is None:
            self._filter_stop_words = self._index_type == "fulltext"
        else:
            self._filter_stop_words = filter_stop_words

        # Create settings for Neo4jClient with merged values
        self._client_settings = Neo4jSettings(
            uri=effective_uri,
            username=effective_username,
            password=effective_password,
        )

        # Runtime state - use shared Neo4jClient
        self._client: Neo4jClient | None = None

    async def __aenter__(self) -> Self:
        """Connect to Neo4j using the shared client."""
        if not self._client_settings.is_configured:
            raise ValueError(
                "Neo4j connection requires uri, username, and password. "
                "Set via constructor or NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars."
            )

        self._client = Neo4jClient(self._client_settings)
        await self._client.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Close Neo4j connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if the provider is connected to Neo4j."""
        return self._client is not None and self._client.driver is not None

    async def _embed(self, text: str) -> list[float]:
        """Embed text using the configured vectorizer."""
        if self._vectorizer is None:
            raise ValueError("No vectorizer configured")
        return await self._vectorizer.aembed(text)

    def _extract_keywords(self, text: str) -> str:
        """Extract keywords from text by removing stop words.

        Used for fulltext search to improve query results when users
        ask natural language questions like "What maintenance issues
        involve engine vibration?" - extracting just "maintenance engine vibration".

        Args:
            text: The input text (typically a user question).

        Returns:
            Space-separated keywords with stop words removed.
        """
        # Remove punctuation and split into words
        words = re.findall(r"\b\w+\b", text.lower())
        # Filter stop words and single characters
        keywords = [w for w in words if w not in FULLTEXT_STOP_WORDS and len(w) > 1]
        return " ".join(keywords)

    def _format_result(self, record: dict[str, Any]) -> str:
        """Format a search result record as text for context."""
        parts: list[str] = []

        # Always include score if present
        score = record.get("score")
        if score is not None:
            parts.append(f"[Score: {score:.3f}]")

        # Include any metadata fields (not text or score)
        for key, value in record.items():
            if key in ("text", "score"):
                continue
            if value is None:
                continue
            parts.append(self._format_field(key, value))

        # Always include text last
        text = record.get("text")
        if text:
            parts.append(str(text))

        return " ".join(parts)

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

    async def _vector_search(self, query_text: str) -> list[dict[str, Any]]:
        """
        Vector search using db.index.vector.queryNodes().

        Args:
            query_text: The full concatenated message text to search for.

        Returns:
            List of result records from the query.
        """
        if self._client is None:
            raise ValueError("Not connected to Neo4j")

        # Embed the full query text (no entity extraction)
        query_embedding = await self._embed(query_text)

        # Build Cypher: index search + retrieval query
        cypher = f"""
        CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
        YIELD node, score
        {self._retrieval_query}
        """

        return await self._client.execute_query(
            cypher,
            {
                "index_name": self._index_name,
                "top_k": self._top_k,
                "embedding": query_embedding,
            },
        )

    async def _fulltext_search(self, query_text: str) -> list[dict[str, Any]]:
        """
        Fulltext search using db.index.fulltext.queryNodes().

        Args:
            query_text: The full concatenated message text to search for.

        Returns:
            List of result records from the query.
        """
        if self._client is None:
            raise ValueError("Not connected to Neo4j")

        # Extract keywords if stop word filtering is enabled
        # This converts "What maintenance issues involve engine vibration?"
        # to "maintenance issues engine vibration" for better Lucene matching
        if self._filter_stop_words:
            query_text = self._extract_keywords(query_text)
            if not query_text.strip():
                return []  # No keywords found after filtering

        # Build Cypher: index search + retrieval query
        cypher = f"""
        CALL db.index.fulltext.queryNodes($index_name, $query)
        YIELD node, score
        WITH node, score
        LIMIT $top_k
        {self._retrieval_query}
        """

        return await self._client.execute_query(
            cypher,
            {
                "index_name": self._index_name,
                "query": query_text,
                "top_k": self._top_k,
            },
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

        # Perform search based on index type
        if self._index_type == "vector":
            results = await self._vector_search(query_text)
        else:
            results = await self._fulltext_search(query_text)

        if not results:
            return Context()

        # Format as context messages (like Azure AI Search)
        context_messages = [ChatMessage(role=Role.USER, text=self._context_prompt)]
        for record in results:
            formatted = self._format_result(record)
            if formatted:
                context_messages.append(ChatMessage(role=Role.USER, text=formatted))

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

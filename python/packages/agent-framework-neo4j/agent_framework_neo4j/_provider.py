"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j using vector, fulltext, or hybrid search
via neo4j-graphrag retrievers, with optional graph enrichment.

Also supports agent memory by storing conversation messages as Memory nodes
and retrieving relevant past messages using semantic search.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import MutableSequence, Sequence
from typing import Any

import neo4j
from agent_framework import ChatMessage, Context, ContextProvider, Role
from neo4j_graphrag.embeddings import Embedder
from neo4j_graphrag.retrievers import (
    HybridCypherRetriever,
    HybridRetriever,
    VectorCypherRetriever,
    VectorRetriever,
)
from neo4j_graphrag.types import RetrieverResult, RetrieverResultItem

from ._config import DEFAULT_CONTEXT_PROMPT, IndexType, MemoryRole, ProviderConfig
from ._fulltext import FulltextRetriever
from ._memory import MemoryManager, ScopeFilter
from ._settings import Neo4jSettings

if sys.version_info >= (3, 12):
    from typing import Self, override
else:
    from typing_extensions import Self, override


# Type alias for all supported retrievers
RetrieverType = VectorRetriever | VectorCypherRetriever | HybridRetriever | HybridCypherRetriever | FulltextRetriever


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
        for _key, value in data.items():
            if isinstance(value, str):
                content = value
                break
    if content is None:
        content = str(record)

    # All remaining fields go to metadata
    return RetrieverResultItem(content=str(content), metadata=data if data else None)


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
        # Search parameters
        top_k: int = 5,
        context_prompt: str = DEFAULT_CONTEXT_PROMPT,
        # Graph enrichment - Cypher query for traversal after index search
        retrieval_query: str | None = None,
        # Embedder for vector/hybrid search (neo4j-graphrag Embedder)
        embedder: Embedder | None = None,
        # Message history (like Azure AI Search's agentic mode)
        message_history_count: int = 10,
        # Fulltext search options
        filter_stop_words: bool | None = None,
        # Memory configuration (Phase 1)
        memory_enabled: bool = False,
        memory_label: str = "Memory",
        memory_roles: tuple[MemoryRole, ...] = ("user", "assistant"),
        # Memory index configuration (Phase 1B - lazy initialization)
        overwrite_memory_index: bool = False,
        memory_vector_index_name: str = "memory_embeddings",
        memory_fulltext_index_name: str = "memory_fulltext",
        # Scoping parameters for multi-tenancy (following Mem0/Redis patterns)
        application_id: str | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        thread_id: str | None = None,
        scope_to_per_operation_thread_id: bool = False,
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
            top_k: Number of results to retrieve.
            context_prompt: Prompt prepended to context.
            retrieval_query: Optional Cypher query for graph enrichment.
                If provided, runs after index search to traverse the graph.
                Must use `node` and `score` variables from index search.
            embedder: neo4j-graphrag Embedder for vector/hybrid search.
                Required when index_type is "vector" or "hybrid".
            message_history_count: Number of recent messages to use for query.
            filter_stop_words: Filter common stop words from fulltext queries.
                Defaults to True for fulltext indexes, False otherwise.
            memory_enabled: Enable storing conversation messages as Memory nodes.
            memory_label: Node label for stored memories. Default: "Memory".
            memory_roles: Which message roles to store. Default: ("user", "assistant").
            overwrite_memory_index: Recreate memory indexes even if they exist.
            memory_vector_index_name: Name of vector index for memories.
            memory_fulltext_index_name: Name of fulltext index for memories.
            application_id: Application ID for scoping memories.
            agent_id: Agent ID for scoping memories.
            user_id: User ID for scoping memories.
            thread_id: Thread ID for scoping memories.
            scope_to_per_operation_thread_id: Use per-operation thread ID for scoping.

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
        self._config = ProviderConfig(
            uri=effective_uri,
            username=effective_username,
            password=effective_password,
            index_name=effective_index_name,
            index_type=index_type,
            fulltext_index_name=fulltext_index_name,
            retrieval_query=retrieval_query,
            top_k=top_k,
            context_prompt=context_prompt,
            message_history_count=message_history_count,
            filter_stop_words=filter_stop_words,
            embedder=embedder,
            # Memory configuration
            memory_enabled=memory_enabled,
            memory_label=memory_label,
            memory_roles=memory_roles,
            # Memory index configuration
            overwrite_memory_index=overwrite_memory_index,
            memory_vector_index_name=memory_vector_index_name,
            memory_fulltext_index_name=memory_fulltext_index_name,
            # Scoping parameters
            application_id=application_id,
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            scope_to_per_operation_thread_id=scope_to_per_operation_thread_id,
        )

        # Extract commonly accessed values to instance attributes
        # (Following Pure Pydantic Settings pattern from Azure AI Search provider)
        self._index_name = self._config.index_name
        self._index_type = self._config.index_type
        self._retrieval_query = self._config.retrieval_query
        self._top_k = self._config.top_k
        self._context_prompt = self._config.context_prompt
        self._message_history_count = self._config.message_history_count

        # Stop word filtering - default to True for fulltext, False otherwise
        if self._config.filter_stop_words is None:
            self._filter_stop_words = self._index_type == "fulltext"
        else:
            self._filter_stop_words = self._config.filter_stop_words

        # Memory configuration
        self._memory_enabled = self._config.memory_enabled
        self._memory_label = self._config.memory_label
        self._memory_roles = set(self._config.memory_roles)

        # Memory index configuration (Phase 1B - lazy initialization)
        self._overwrite_memory_index = self._config.overwrite_memory_index
        self._memory_vector_index_name = self._config.memory_vector_index_name
        self._memory_fulltext_index_name = self._config.memory_fulltext_index_name

        # Scoping parameters (following Mem0/Redis patterns)
        self.application_id = self._config.application_id
        self.agent_id = self._config.agent_id
        self.user_id = self._config.user_id
        self.thread_id = self._config.thread_id
        self.scope_to_per_operation_thread_id = self._config.scope_to_per_operation_thread_id

        # Create memory manager if memory is enabled (delegates memory operations)
        if self._memory_enabled:
            self._memory_manager: MemoryManager | None = MemoryManager(
                memory_label=self._memory_label,
                memory_roles=self._memory_roles,
                memory_vector_index_name=self._memory_vector_index_name,
                memory_fulltext_index_name=self._memory_fulltext_index_name,
                overwrite_memory_index=self._overwrite_memory_index,
                embedder=self._config.embedder,
            )
        else:
            self._memory_manager = None

        # Runtime state
        self._driver: neo4j.Driver | None = None
        self._retriever: RetrieverType | None = None
        self._per_operation_thread_id: str | None = None

    def _create_retriever(self) -> RetrieverType:
        """Create the appropriate neo4j-graphrag retriever based on configuration."""
        if self._driver is None:
            raise ValueError("Driver not initialized")

        # Determine if graph enrichment is enabled (retrieval_query provided)
        use_graph_enrichment = self._retrieval_query is not None

        if self._index_type == "vector":
            if use_graph_enrichment:
                return VectorCypherRetriever(
                    driver=self._driver,
                    index_name=self._index_name,
                    retrieval_query=self._config.get_retrieval_query(),
                    embedder=self._config.get_embedder(),
                    result_formatter=_format_cypher_result,
                )
            else:
                return VectorRetriever(
                    driver=self._driver,
                    index_name=self._index_name,
                    embedder=self._config.get_embedder(),
                )

        elif self._index_type == "hybrid":
            if use_graph_enrichment:
                return HybridCypherRetriever(
                    driver=self._driver,
                    vector_index_name=self._index_name,
                    fulltext_index_name=self._config.get_fulltext_index_name(),
                    retrieval_query=self._config.get_retrieval_query(),
                    embedder=self._config.get_embedder(),
                    result_formatter=_format_cypher_result,
                )
            else:
                return HybridRetriever(
                    driver=self._driver,
                    vector_index_name=self._index_name,
                    fulltext_index_name=self._config.get_fulltext_index_name(),
                    embedder=self._config.get_embedder(),
                )

        else:  # fulltext
            return FulltextRetriever(
                driver=self._driver,
                index_name=self._index_name,
                retrieval_query=self._retrieval_query,
                filter_stop_words=self._filter_stop_words,
                result_formatter=_format_cypher_result if use_graph_enrichment else None,
            )

    @property
    def _effective_thread_id(self) -> str | None:
        """Resolve the active thread ID.

        Returns per-operation thread ID when scoping is enabled;
        otherwise the provider's configured thread_id.
        """
        if self.scope_to_per_operation_thread_id:
            return self._per_operation_thread_id
        return self.thread_id

    def _validate_per_operation_thread_id(self, thread_id: str | None) -> None:
        """Validate that a new thread ID doesn't conflict when scoped.

        Prevents cross-thread data leakage by enforcing single-thread usage
        when per-operation scoping is enabled.

        Args:
            thread_id: The new thread ID or None.

        Raises:
            ValueError: If a new thread ID conflicts with the existing one.
        """
        if (
            self.scope_to_per_operation_thread_id
            and thread_id
            and self._per_operation_thread_id
            and thread_id != self._per_operation_thread_id
        ):
            raise ValueError(
                "Neo4jContextProvider can only be used with one thread at a time "
                "when scope_to_per_operation_thread_id is True."
            )

    @override
    async def thread_created(self, thread_id: str | None) -> None:
        """Called when a new conversation thread is created.

        Captures the per-operation thread ID when scoping is enabled.

        Args:
            thread_id: The ID of the thread or None.
        """
        self._validate_per_operation_thread_id(thread_id)
        self._per_operation_thread_id = self._per_operation_thread_id or thread_id

    @override
    async def __aenter__(self) -> Self:
        """Connect to Neo4j and create retriever."""
        # Get validated connection config (raises if not all set)
        uri, username, password = self._config.get_connection()

        # Create driver
        self._driver = neo4j.GraphDatabase.driver(
            uri,
            auth=(username, password),
        )

        # Verify connectivity (sync call wrapped for async)
        await asyncio.to_thread(self._driver.verify_connectivity)

        # Create retriever in thread pool because neo4j-graphrag retrievers
        # call _fetch_index_infos() during __init__ which makes DB calls
        self._retriever = await asyncio.to_thread(self._create_retriever)

        return self

    @override
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

    async def _execute_search(self, query_text: str) -> RetrieverResult:
        """Execute search using the configured retriever."""
        if self._retriever is None:
            raise ValueError("Retriever not initialized")

        # neo4j-graphrag retrievers are sync, wrap with asyncio.to_thread
        return await asyncio.to_thread(
            self._retriever.search,
            query_text=query_text,
            top_k=self._top_k,
        )

    def _get_scope_filter(self) -> ScopeFilter:
        """Build current scope filter from provider state.

        Returns:
            ScopeFilter with current scoping parameters.
        """
        return ScopeFilter(
            application_id=self.application_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            thread_id=self._effective_thread_id,
        )

    @property
    def _memory_indexes_initialized(self) -> bool:
        """Check if memory indexes have been initialized (delegates to MemoryManager)."""
        if self._memory_manager is None:
            return False
        return self._memory_manager.indexes_initialized

    async def _search_memories(self, query_text: str) -> list[dict[str, Any]]:
        """Search Memory nodes with scoping filters (delegates to MemoryManager).

        Args:
            query_text: The query text to search for.

        Returns:
            List of memory dictionaries with text and metadata.
        """
        if self._driver is None or self._memory_manager is None:
            return []

        scope = self._get_scope_filter()
        return await self._memory_manager.search(
            driver=self._driver,
            query_text=query_text,
            scope=scope,
            top_k=self._top_k,
        )

    @override
    async def invoking(
        self,
        messages: ChatMessage | MutableSequence[ChatMessage],
        **_kwargs: Any,
    ) -> Context:
        """
        Called before each LLM invocation to provide context.

        Key design: NO entity extraction. The full message text is passed
        to the index search, which handles relevance ranking.

        When memory_enabled is True, also searches stored memories with
        scoping filters and includes relevant past conversations in context.
        """
        # Not connected - return empty context
        if not self.is_connected:
            return Context()

        # Convert to list - handle both single message and sequence
        if isinstance(messages, ChatMessage):
            messages_list = [messages]
        else:
            messages_list = list(messages)

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

        context_messages: list[ChatMessage] = []

        # Perform knowledge graph search using retriever
        result = await self._execute_search(query_text)
        if result.items:
            context_messages.append(ChatMessage(role=Role.USER, text=self._context_prompt))
            formatted_results = self._format_retriever_result(result)
            for text in formatted_results:
                if text:
                    context_messages.append(ChatMessage(role=Role.USER, text=text))

        # Search memories if memory is enabled
        if self._memory_enabled:
            memories = await self._search_memories(query_text)
            if memories:
                memory_prompt = "## Conversation Memory\nRelevant information from past conversations:"
                context_messages.append(ChatMessage(role=Role.USER, text=memory_prompt))
                for memory in memories:
                    memory_text = f"[{memory.get('role', 'unknown')}]: {memory.get('text', '')}"
                    if memory.get("timestamp"):
                        memory_text = f"[{memory['timestamp']}] {memory_text}"
                    context_messages.append(ChatMessage(role=Role.USER, text=memory_text))

        if not context_messages:
            return Context()

        return Context(messages=context_messages)

    async def _ensure_memory_indexes(self) -> None:
        """Create memory indexes if they don't exist (delegates to MemoryManager).

        Raises:
            ValueError: If driver not initialized or memory not enabled.
        """
        if self._driver is None:
            raise ValueError("Driver not initialized - cannot create memory indexes")
        if self._memory_manager is None:
            raise ValueError("Memory not enabled - cannot create memory indexes")

        await self._memory_manager.ensure_indexes(self._driver)

    @override
    async def invoked(
        self,
        request_messages: ChatMessage | Sequence[ChatMessage],
        response_messages: ChatMessage | Sequence[ChatMessage] | None = None,
        invoke_exception: Exception | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Called after agent model invocation to store conversation memories.

        When memory_enabled is True, stores request and response messages
        as Memory nodes in Neo4j with scoping metadata for later retrieval.

        Args:
            request_messages: Messages sent to the model.
            response_messages: Messages received from the model.
            invoke_exception: Any exception that occurred during invocation.
            **kwargs: Additional keyword arguments (unused).
        """
        # Skip if memory is disabled or not connected
        if not self._memory_enabled or self._driver is None or self._memory_manager is None:
            return

        # Ensure memory indexes exist (lazy initialization - first use creates indexes)
        await self._memory_manager.ensure_indexes(self._driver)

        # Convert to lists (following Mem0/Redis patterns)
        request_list = (
            [request_messages]
            if isinstance(request_messages, ChatMessage)
            else list(request_messages)
        )
        response_list = (
            [response_messages]
            if isinstance(response_messages, ChatMessage)
            else list(response_messages)
            if response_messages
            else []
        )

        # Combine all messages and store via MemoryManager
        all_messages = [*request_list, *response_list]
        scope = self._get_scope_filter()
        await self._memory_manager.store(self._driver, all_messages, scope)

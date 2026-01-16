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
import uuid
from collections.abc import MutableSequence, Sequence
from datetime import datetime, timezone
from typing import Any, Literal

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
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ._fulltext import FulltextRetriever
from ._settings import Neo4jSettings

if sys.version_info >= (3, 12):
    from typing import Self, override
else:
    from typing_extensions import Self, override


# Roles that can be stored as memories
MemoryRole = Literal["user", "assistant", "system"]


# Type alias for all supported retrievers
RetrieverType = VectorRetriever | VectorCypherRetriever | HybridRetriever | HybridCypherRetriever | FulltextRetriever

# Type alias for index types
IndexType = Literal["vector", "fulltext", "hybrid"]

# Default context prompt for Neo4j knowledge graph context
_DEFAULT_CONTEXT_PROMPT = (
    "## Knowledge Graph Context\n"
    "Use the following information from the knowledge graph to answer the question:"
)


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


class ConnectionConfig(BaseModel):
    """Validated Neo4j connection configuration with non-optional types."""

    model_config = ConfigDict(frozen=True)

    uri: str
    username: str
    password: str


class ProviderConfig(BaseModel):
    """
    Pydantic model for Neo4jContextProvider configuration validation.

    Validates all configuration parameters and their interdependencies.
    After validation, use the get_* methods for type-safe access to
    conditionally required fields.
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

    # Graph enrichment (optional Cypher query for traversal)
    retrieval_query: str | None = None

    # Search parameters
    top_k: int = 5
    context_prompt: str = _DEFAULT_CONTEXT_PROMPT
    message_history_count: int = 10
    filter_stop_words: bool | None = None

    # Embedder (validated separately due to complex type)
    embedder: Embedder | None = None

    # Memory configuration (Phase 1)
    memory_enabled: bool = False
    memory_label: str = "Memory"
    memory_roles: tuple[MemoryRole, ...] = ("user", "assistant")

    # Scoping parameters for multi-tenancy (following Mem0/Redis patterns)
    application_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    thread_id: str | None = None
    scope_to_per_operation_thread_id: bool = False

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

    @field_validator("memory_roles")
    @classmethod
    def memory_roles_must_be_valid(cls, v: tuple[MemoryRole, ...]) -> tuple[MemoryRole, ...]:
        valid_roles = {"user", "assistant", "system"}
        for role in v:
            if role not in valid_roles:
                raise ValueError(f"Invalid memory role: {role}. Must be one of {valid_roles}")
        return v

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        """Validate interdependent configuration options."""
        # Hybrid search requires fulltext index
        if self.index_type == "hybrid" and not self.fulltext_index_name:
            raise ValueError(
                "fulltext_index_name is required when index_type='hybrid'"
            )

        # Vector/hybrid search requires embedder
        if self.index_type in ("vector", "hybrid") and self.embedder is None:
            raise ValueError(
                f"embedder is required when index_type='{self.index_type}'"
            )

        # Memory requires at least one scope filter (following Mem0/Redis pattern)
        if self.memory_enabled:
            has_scope = any([
                self.application_id,
                self.agent_id,
                self.user_id,
                self.thread_id,
            ])
            if not has_scope:
                raise ValueError(
                    "Memory requires at least one scope filter: "
                    "application_id, agent_id, user_id, or thread_id"
                )

        return self

    # Type-safe accessors for conditionally required fields
    # These return non-optional types after validation guarantees

    def get_retrieval_query(self) -> str:
        """Get retrieval_query - raises if not set."""
        if self.retrieval_query is None:
            raise ValueError("retrieval_query not set")
        return self.retrieval_query

    def get_fulltext_index_name(self) -> str:
        """Get fulltext_index_name (guaranteed set for hybrid mode)."""
        if self.fulltext_index_name is None:
            raise ValueError("fulltext_index_name not set")
        return self.fulltext_index_name

    def get_embedder(self) -> Embedder:
        """Get embedder (guaranteed set for vector/hybrid mode)."""
        if self.embedder is None:
            raise ValueError("embedder not set")
        return self.embedder

    def get_connection(self) -> ConnectionConfig:
        """Get validated connection config - raises if not all fields set."""
        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Neo4j connection requires uri, username, and password. "
                "Set via constructor or NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars."
            )
        return ConnectionConfig(
            uri=self.uri,
            username=self.username,
            password=self.password,
        )


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
        context_prompt: str = _DEFAULT_CONTEXT_PROMPT,
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
            # Scoping parameters
            application_id=application_id,
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            scope_to_per_operation_thread_id=scope_to_per_operation_thread_id,
        )

        # Store commonly accessed values for convenience
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

        # Scoping parameters (following Mem0/Redis patterns)
        self.application_id = self._config.application_id
        self.agent_id = self._config.agent_id
        self.user_id = self._config.user_id
        self.thread_id = self._config.thread_id
        self.scope_to_per_operation_thread_id = self._config.scope_to_per_operation_thread_id

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
        conn = self._config.get_connection()

        # Create driver
        self._driver = neo4j.GraphDatabase.driver(
            conn.uri,
            auth=(conn.username, conn.password),
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

    def _build_scope_filter_cypher(self) -> tuple[str, dict[str, Any]]:
        """Build Cypher WHERE clause for scoping filters.

        Returns:
            Tuple of (WHERE clause string, parameters dict).
        """
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if self.application_id:
            conditions.append("m.application_id = $application_id")
            params["application_id"] = self.application_id
        if self.agent_id:
            conditions.append("m.agent_id = $agent_id")
            params["agent_id"] = self.agent_id
        if self.user_id:
            conditions.append("m.user_id = $user_id")
            params["user_id"] = self.user_id
        if self._effective_thread_id:
            conditions.append("m.thread_id = $thread_id")
            params["thread_id"] = self._effective_thread_id

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    async def _search_memories(self, query_text: str) -> list[dict[str, Any]]:
        """Search Memory nodes with scoping filters.

        Uses vector similarity if embedder is configured, otherwise falls back
        to returning recent memories ordered by timestamp.

        Args:
            query_text: The query text to search for.

        Returns:
            List of memory dictionaries with text and metadata.
        """
        if self._driver is None:
            return []

        where_clause, params = self._build_scope_filter_cypher()
        params["top_k"] = self._top_k

        embedder = self._config.embedder
        if embedder is not None:
            # Vector similarity search on Memory nodes
            query_embedding = await asyncio.to_thread(embedder.embed_query, query_text)
            params["query_embedding"] = query_embedding

            # Use vector index if available, otherwise compute similarity
            cypher = f"""
            MATCH (m:{self._memory_label})
            WHERE {where_clause}
            AND m.embedding IS NOT NULL
            WITH m, gds.similarity.cosine(m.embedding, $query_embedding) AS score
            ORDER BY score DESC
            LIMIT $top_k
            RETURN m.text AS text, m.role AS role, m.timestamp AS timestamp, score
            """
        else:
            # Fallback: return recent memories by timestamp
            cypher = f"""
            MATCH (m:{self._memory_label})
            WHERE {where_clause}
            ORDER BY m.timestamp DESC
            LIMIT $top_k
            RETURN m.text AS text, m.role AS role, m.timestamp AS timestamp, 1.0 AS score
            """

        def _execute_read() -> list[dict[str, Any]]:
            with self._driver.session() as session:  # type: ignore[union-attr]
                result = session.run(cypher, **params)
                return [dict(record) for record in result]

        return await asyncio.to_thread(_execute_read)

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
        result = await self._search(query_text)
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

    async def _store_memories(self, messages: list[ChatMessage]) -> None:
        """Store messages as Memory nodes in Neo4j.

        Creates Memory nodes with text, role, timestamp, and scoping metadata.
        Optionally generates embeddings if an embedder is configured.

        Args:
            messages: List of ChatMessage objects to store.
        """
        if not messages or self._driver is None:
            return

        # Filter to configured roles with non-empty text
        memories_to_store: list[dict[str, Any]] = []
        for msg in messages:
            role_value = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if role_value not in self._memory_roles:
                continue
            if not msg.text or not msg.text.strip():
                continue

            memory_data: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "text": msg.text,
                "role": role_value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                # Scoping fields
                "application_id": self.application_id,
                "agent_id": self.agent_id,
                "user_id": self.user_id,
                "thread_id": self._effective_thread_id,
            }

            # Add optional message metadata if available
            if hasattr(msg, "message_id") and msg.message_id:
                memory_data["message_id"] = msg.message_id
            if hasattr(msg, "author_name") and msg.author_name:
                memory_data["author_name"] = msg.author_name

            memories_to_store.append(memory_data)

        if not memories_to_store:
            return

        # Generate embeddings if embedder is configured (for vector search on memories)
        embedder = self._config.embedder
        if embedder is not None:
            texts = [m["text"] for m in memories_to_store]
            # neo4j-graphrag embedders are sync, wrap with asyncio.to_thread
            embeddings = await asyncio.to_thread(embedder.embed_query, texts[0])
            # For batch, we need to embed each text
            for i, memory in enumerate(memories_to_store):
                if i == 0:
                    memory["embedding"] = embeddings
                else:
                    memory["embedding"] = await asyncio.to_thread(
                        embedder.embed_query, memory["text"]
                    )

        # Build Cypher query for creating Memory nodes
        # Use UNWIND for batch creation
        cypher = f"""
        UNWIND $memories AS memory
        CREATE (m:{self._memory_label})
        SET m.id = memory.id,
            m.text = memory.text,
            m.role = memory.role,
            m.timestamp = memory.timestamp,
            m.application_id = memory.application_id,
            m.agent_id = memory.agent_id,
            m.user_id = memory.user_id,
            m.thread_id = memory.thread_id
        """

        # Add optional fields if present
        if any("message_id" in m for m in memories_to_store):
            cypher += ",\n            m.message_id = memory.message_id"
        if any("author_name" in m for m in memories_to_store):
            cypher += ",\n            m.author_name = memory.author_name"
        if any("embedding" in m for m in memories_to_store):
            cypher += ",\n            m.embedding = memory.embedding"

        # Execute in thread pool (neo4j driver is sync)
        def _execute_write() -> None:
            with self._driver.session() as session:  # type: ignore[union-attr]
                session.run(cypher, memories=memories_to_store)

        await asyncio.to_thread(_execute_write)

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
        if not self._memory_enabled or self._driver is None:
            return

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

        # Combine all messages
        all_messages = [*request_list, *response_list]

        # Store as Memory nodes
        await self._store_memories(all_messages)

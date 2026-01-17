"""
Memory management for Neo4j Context Provider.

Handles storage and retrieval of conversation memories as Memory nodes
in Neo4j with scoping for multi-tenancy support.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import neo4j
from agent_framework import ChatMessage
from neo4j_graphrag.embeddings import Embedder


@dataclass(frozen=True, slots=True)
class ScopeFilter:
    """Scoping parameters for memory isolation.

    Following Mem0/Redis patterns, memories can be scoped to:
    - application_id: Isolate by application
    - agent_id: Isolate by agent instance
    - user_id: Isolate by user
    - thread_id: Isolate by conversation thread
    """

    application_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    thread_id: str | None = None

    def to_cypher_where(self, alias: str = "m") -> tuple[str, dict[str, Any]]:
        """Build Cypher WHERE clause and parameters for scoping filters.

        Args:
            alias: The node alias to use in the WHERE clause.

        Returns:
            Tuple of (WHERE clause string, parameters dict).
        """
        conditions: list[str] = []
        params: dict[str, Any] = {}

        if self.application_id:
            conditions.append(f"{alias}.application_id = $application_id")
            params["application_id"] = self.application_id
        if self.agent_id:
            conditions.append(f"{alias}.agent_id = $agent_id")
            params["agent_id"] = self.agent_id
        if self.user_id:
            conditions.append(f"{alias}.user_id = $user_id")
            params["user_id"] = self.user_id
        if self.thread_id:
            conditions.append(f"{alias}.thread_id = $thread_id")
            params["thread_id"] = self.thread_id

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params


class MemoryManager:
    """Manages Memory node storage and retrieval in Neo4j.

    Provides lazy index initialization following the RedisProvider pattern,
    semantic search for memory retrieval, and scoped memory storage.
    """

    def __init__(
        self,
        *,
        memory_label: str = "Memory",
        memory_roles: set[str],
        memory_vector_index_name: str = "memory_embeddings",
        memory_fulltext_index_name: str = "memory_fulltext",
        overwrite_memory_index: bool = False,
        embedder: Embedder | None = None,
    ) -> None:
        """Initialize the memory manager.

        Args:
            memory_label: Node label for stored memories.
            memory_roles: Set of roles to store (e.g., {"user", "assistant"}).
            memory_vector_index_name: Name of vector index for memories.
            memory_fulltext_index_name: Name of fulltext index for memories.
            overwrite_memory_index: Recreate indexes even if they exist.
            embedder: Embedder for vector similarity search.
        """
        self._memory_label = memory_label
        self._memory_roles = memory_roles
        self._memory_vector_index_name = memory_vector_index_name
        self._memory_fulltext_index_name = memory_fulltext_index_name
        self._overwrite_memory_index = overwrite_memory_index
        self._embedder = embedder
        self._indexes_initialized = False

    @property
    def indexes_initialized(self) -> bool:
        """Check if memory indexes have been initialized."""
        return self._indexes_initialized

    async def ensure_indexes(self, driver: neo4j.Driver) -> None:
        """Create memory indexes if they don't exist (lazy initialization).

        Following the RedisProvider pattern, this method is called on first
        memory operation and creates necessary indexes for efficient search.
        Uses IF NOT EXISTS for idempotency.

        Creates:
        - Vector index on Memory.embedding (if embedder configured)
        - Fulltext index on Memory.text
        - Standard indexes on scoping fields (user_id, thread_id, etc.)

        Args:
            driver: Neo4j driver for database operations.

        Raises:
            ValueError: If index creation fails.
        """
        # Skip if already initialized (unless overwrite requested)
        if self._indexes_initialized and not self._overwrite_memory_index:
            return

        # Build list of index creation statements
        # Following modern Cypher syntax (no deprecated features)
        index_statements: list[str] = []

        # Vector index (if embedder configured) - requires Neo4j 5.11+
        if self._embedder is not None:
            # Get embedding dimensions by generating a test embedding
            test_embedding = await asyncio.to_thread(
                self._embedder.embed_query, "test"
            )
            dimensions = len(test_embedding)

            if self._overwrite_memory_index:
                # Drop existing index first if overwrite requested
                index_statements.append(
                    f"DROP INDEX {self._memory_vector_index_name} IF EXISTS"
                )

            # Create vector index with proper configuration
            # Note: Neo4j 5.11+ syntax for vector indexes
            index_statements.append(f"""
                CREATE VECTOR INDEX {self._memory_vector_index_name} IF NOT EXISTS
                FOR (m:{self._memory_label})
                ON m.embedding
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
            """)

        # Fulltext index on text property
        if self._overwrite_memory_index:
            index_statements.append(
                f"DROP INDEX {self._memory_fulltext_index_name} IF EXISTS"
            )

        index_statements.append(f"""
            CREATE FULLTEXT INDEX {self._memory_fulltext_index_name} IF NOT EXISTS
            FOR (m:{self._memory_label})
            ON EACH [m.text]
        """)

        # Standard indexes on scoping fields for efficient filtering
        scoping_fields = ["user_id", "thread_id", "agent_id", "application_id"]
        for field in scoping_fields:
            index_name = f"memory_{field}"
            if self._overwrite_memory_index:
                index_statements.append(f"DROP INDEX {index_name} IF EXISTS")
            index_statements.append(f"""
                CREATE INDEX {index_name} IF NOT EXISTS
                FOR (m:{self._memory_label})
                ON (m.{field})
            """)

        # Execute index creation statements
        def _execute_index_creation() -> None:
            with driver.session() as session:
                for statement in index_statements:
                    try:
                        session.run(statement.strip())
                    except Exception as e:
                        # Provide helpful error for common issues
                        error_msg = str(e).lower()
                        if "vector" in error_msg and "not supported" in error_msg:
                            raise ValueError(
                                f"Vector index creation failed. Neo4j 5.11+ required. "
                                f"Original error: {e}"
                            ) from e
                        raise

        await asyncio.to_thread(_execute_index_creation)
        self._indexes_initialized = True

    async def store(
        self,
        driver: neo4j.Driver,
        messages: list[ChatMessage],
        scope: ScopeFilter,
    ) -> None:
        """Store messages as Memory nodes in Neo4j.

        Creates Memory nodes with text, role, timestamp, and scoping metadata.
        Optionally generates embeddings if an embedder is configured.

        Args:
            driver: Neo4j driver for database operations.
            messages: List of ChatMessage objects to store.
            scope: Scoping filter for memory isolation.
        """
        if not messages:
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
                # Scoping fields from ScopeFilter
                "application_id": scope.application_id,
                "agent_id": scope.agent_id,
                "user_id": scope.user_id,
                "thread_id": scope.thread_id,
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
        if self._embedder is not None:
            # neo4j-graphrag embedders are sync, wrap with asyncio.to_thread
            for memory in memories_to_store:
                memory["embedding"] = await asyncio.to_thread(
                    self._embedder.embed_query, memory["text"]
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
            with driver.session() as session:
                session.run(cypher, memories=memories_to_store)

        await asyncio.to_thread(_execute_write)

    async def search(
        self,
        driver: neo4j.Driver,
        query_text: str,
        scope: ScopeFilter,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search Memory nodes with scoping filters.

        Uses vector index search if embedder is configured, otherwise falls back
        to returning recent memories ordered by timestamp.

        Args:
            driver: Neo4j driver for database operations.
            query_text: The query text to search for.
            scope: Scoping filter for memory isolation.
            top_k: Maximum number of results to return.

        Returns:
            List of memory dictionaries with text and metadata.
        """
        where_clause, params = scope.to_cypher_where()
        params["top_k"] = top_k

        if self._embedder is not None:
            # Vector similarity search using Neo4j vector index
            query_embedding = await asyncio.to_thread(
                self._embedder.embed_query, query_text
            )
            params["query_embedding"] = query_embedding

            # Use db.index.vector.queryNodes() for proper vector index search
            # This is the recommended approach for Neo4j 5.11+
            cypher = f"""
            CALL db.index.vector.queryNodes($index_name, $top_k, $query_embedding)
            YIELD node AS m, score
            WHERE {where_clause}
            RETURN m.text AS text, m.role AS role, m.timestamp AS timestamp, score
            ORDER BY score DESC
            """
            params["index_name"] = self._memory_vector_index_name
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
            with driver.session() as session:
                result = session.run(cypher, **params)
                return [dict(record) for record in result]

        return await asyncio.to_thread(_execute_read)

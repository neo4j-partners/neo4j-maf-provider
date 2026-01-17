"""
Configuration models for Neo4j Context Provider.

Provides Pydantic-based configuration validation for the Neo4jContextProvider,
including type aliases and default values.
"""

from __future__ import annotations

import sys
from typing import Literal

from neo4j_graphrag.embeddings import Embedder
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

if sys.version_info >= (3, 12):
    from typing import Self
else:
    from typing_extensions import Self


# Roles that can be stored as memories
MemoryRole = Literal["user", "assistant", "system"]

# Type alias for index types
IndexType = Literal["vector", "fulltext", "hybrid"]

# Default context prompt for Neo4j knowledge graph context
DEFAULT_CONTEXT_PROMPT = (
    "## Knowledge Graph Context\n"
    "Use the following information from the knowledge graph to answer the question:"
)


class ProviderConfig(BaseModel):
    """
    Pydantic model for Neo4jContextProvider configuration validation.

    Validates all configuration parameters and their interdependencies.
    After validation, values are extracted to instance attributes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

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
    context_prompt: str = DEFAULT_CONTEXT_PROMPT
    message_history_count: int = 10
    filter_stop_words: bool | None = None

    # Embedder (validated separately due to complex type)
    embedder: Embedder | None = None

    # Memory configuration (Phase 1)
    memory_enabled: bool = False
    memory_label: str = "Memory"
    memory_roles: tuple[MemoryRole, ...] = ("user", "assistant")

    # Memory index configuration (Phase 1B - lazy initialization)
    overwrite_memory_index: bool = False
    memory_vector_index_name: str = "memory_embeddings"
    memory_fulltext_index_name: str = "memory_fulltext"

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

    def get_connection(self) -> tuple[str, str, str]:
        """Get validated connection config - raises if not all fields set."""
        if not all([self.uri, self.username, self.password]):
            raise ValueError(
                "Neo4j connection requires uri, username, and password. "
                "Set via constructor or NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD env vars."
            )
        # Type narrowing - we've verified these are not None
        assert self.uri is not None
        assert self.username is not None
        assert self.password is not None
        return self.uri, self.username, self.password

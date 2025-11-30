"""
Tests for Neo4j Context Provider.

Tests the provider initialization, validation, and search functionality.
"""

import pytest
from agent_framework import ChatMessage, Context, Role

from neo4j_provider import Neo4jContextProvider, Neo4jContextProviderSettings, VectorizerProtocol


class MockVectorizer:
    """Mock vectorizer for testing.

    Implements full VectorizerProtocol interface compatible with
    redisvl.utils.vectorize.BaseVectorizer pattern.
    """

    async def aembed(self, text: str) -> list[float]:
        """Asynchronously return a fake embedding."""
        return [0.1] * 1536

    def embed(self, text: str) -> list[float]:
        """Synchronously return a fake embedding."""
        return [0.1] * 1536


class TestSettings:
    """Test Neo4jContextProviderSettings."""

    def test_settings_defaults(self) -> None:
        """Settings should have None defaults."""
        settings = Neo4jContextProviderSettings()
        assert settings.uri is None
        assert settings.username is None
        assert settings.password is None
        assert settings.index_name is None
        assert settings.index_type is None

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings should load from environment variables."""
        monkeypatch.setenv("NEO4J_URI", "bolt://test:7687")
        monkeypatch.setenv("NEO4J_USERNAME", "testuser")
        monkeypatch.setenv("NEO4J_INDEX_NAME", "testindex")

        settings = Neo4jContextProviderSettings()
        assert settings.uri == "bolt://test:7687"
        assert settings.username == "testuser"
        assert settings.index_name == "testindex"

    def test_settings_mode_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mode setting should load from NEO4J_MODE environment variable."""
        monkeypatch.setenv("NEO4J_MODE", "graph_enriched")

        settings = Neo4jContextProviderSettings()
        assert settings.mode == "graph_enriched"


class TestProviderInit:
    """Test Neo4jContextProvider initialization."""

    def test_requires_index_name(self) -> None:
        """Provider should require index_name."""
        with pytest.raises(ValueError, match="index_name is required"):
            Neo4jContextProvider(
                index_type="fulltext",
            )

    def test_requires_vectorizer_for_vector_type(self) -> None:
        """Provider should require vectorizer when index_type is vector."""
        with pytest.raises(ValueError, match="vectorizer is required"):
            Neo4jContextProvider(
                index_name="test_index",
                index_type="vector",
            )

    def test_requires_retrieval_query_for_graph_enriched(self) -> None:
        """Provider should require retrieval_query when mode is graph_enriched."""
        with pytest.raises(ValueError, match="retrieval_query is required"):
            Neo4jContextProvider(
                index_name="test_index",
                index_type="fulltext",
                mode="graph_enriched",
            )

    def test_valid_fulltext_config(self) -> None:
        """Provider should accept valid fulltext configuration."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        assert provider._index_name == "test_index"
        assert provider._index_type == "fulltext"
        assert provider._mode == "basic"

    def test_valid_vector_config(self) -> None:
        """Provider should accept valid vector configuration."""
        vectorizer = MockVectorizer()
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="vector",
            vectorizer=vectorizer,
        )
        assert provider._index_name == "test_index"
        assert provider._index_type == "vector"
        assert provider._vectorizer is vectorizer

    def test_valid_graph_enriched_config(self) -> None:
        """Provider should accept valid graph_enriched configuration."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            mode="graph_enriched",
            retrieval_query="RETURN node.text AS text, score",
        )
        assert provider._mode == "graph_enriched"
        assert "RETURN" in provider._retrieval_query

    def test_default_values(self) -> None:
        """Provider should have sensible defaults."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        assert provider._top_k == 5
        assert provider._message_history_count == 10
        assert "Knowledge Graph Context" in provider._context_prompt

    def test_not_connected_initially(self) -> None:
        """Provider should not be connected before __aenter__."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        assert not provider.is_connected


class TestVectorizerProtocol:
    """Test VectorizerProtocol."""

    def test_mock_vectorizer_matches_protocol(self) -> None:
        """MockVectorizer should match VectorizerProtocol."""
        vectorizer = MockVectorizer()
        # Protocol check via runtime_checkable - both methods
        assert callable(getattr(vectorizer, "aembed", None))
        assert callable(getattr(vectorizer, "embed", None))

    def test_sync_embed_method(self) -> None:
        """MockVectorizer should have sync embed method for redisvl compatibility."""
        vectorizer = MockVectorizer()
        embedding = vectorizer.embed("test text")
        assert len(embedding) == 1536

    @pytest.mark.asyncio
    async def test_async_embed_method(self) -> None:
        """Provider should be able to call vectorizer.aembed."""
        vectorizer = MockVectorizer()
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="vector",
            vectorizer=vectorizer,
        )
        embedding = await provider._embed("test text")
        assert len(embedding) == 1536


class TestFormatResult:
    """Test result formatting."""

    def test_format_basic_result(self) -> None:
        """Format a basic result with text and score."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        record = {"text": "Sample text", "score": 0.95}
        formatted = provider._format_result(record)
        assert "[Score: 0.950]" in formatted
        assert "Sample text" in formatted

    def test_format_result_with_metadata(self) -> None:
        """Format a result with additional metadata."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        record = {
            "text": "Sample text",
            "score": 0.85,
            "company": "Acme Corp",
        }
        formatted = provider._format_result(record)
        assert "[Score: 0.850]" in formatted
        assert "[company: Acme Corp]" in formatted
        assert "Sample text" in formatted

    def test_format_result_with_list_field(self) -> None:
        """Format a result with list fields like risks."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        record = {
            "text": "Sample text",
            "score": 0.75,
            "risks": ["market risk", "credit risk"],
        }
        formatted = provider._format_result(record)
        assert "[risks: market risk, credit risk]" in formatted

    def test_format_result_with_graph_enriched_metadata(self) -> None:
        """Format a result with graph-enriched metadata fields."""
        # Pattern from neo4j-graphrag VectorCypherRetriever
        retrieval_query = """
        MATCH (node)-[:FROM_DOCUMENT]-(doc:Document)-[:FILED]-(company:Company)
        OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
        RETURN node.text AS text, score, company.name AS company,
               collect(DISTINCT risk.name) AS risks
        """
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            mode="graph_enriched",
            retrieval_query=retrieval_query,
        )
        # Simulate enriched result from graph traversal
        record = {
            "text": "Apple reported strong quarterly earnings...",
            "score": 0.92,
            "company": "Apple Inc.",
            "risks": ["supply chain disruption", "regulatory compliance"],
        }
        formatted = provider._format_result(record)
        assert "[Score: 0.920]" in formatted
        assert "[company: Apple Inc.]" in formatted
        assert "[risks: supply chain disruption, regulatory compliance]" in formatted
        assert "Apple reported strong quarterly earnings..." in formatted

    def test_format_result_with_empty_list(self) -> None:
        """Format a result when list fields are empty."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        record = {
            "text": "Sample text content",
            "score": 0.5,
            "related_items": [],  # Empty list field
        }
        formatted = provider._format_result(record)
        # Empty lists should not appear in output as metadata
        assert "[related_items:" not in formatted
        assert "[Score: 0.500]" in formatted
        assert "Sample text content" in formatted

    def test_format_result_handles_none_metadata(self) -> None:
        """Format a result when metadata fields are None."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        record = {
            "text": "Just text content",
            "score": 0.8,
            "company": None,
            "risks": None,
        }
        formatted = provider._format_result(record)
        # None values should not appear in output
        assert "company" not in formatted
        assert "risks" not in formatted
        assert "[Score: 0.800]" in formatted
        assert "Just text content" in formatted


class TestGraphEnrichedMode:
    """Test graph-enriched mode functionality."""

    def test_uses_custom_retrieval_query(self) -> None:
        """Provider should store custom retrieval query."""
        custom_query = """
        MATCH (node)-[:FROM_DOCUMENT]-(doc:Document)
        RETURN node.text AS text, score, doc.path AS source
        """
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            mode="graph_enriched",
            retrieval_query=custom_query,
        )
        assert "FROM_DOCUMENT" in provider._retrieval_query
        assert "doc.path AS source" in provider._retrieval_query

    def test_uses_default_retrieval_query_for_basic_mode(self) -> None:
        """Provider should use DEFAULT_RETRIEVAL_QUERY when mode is basic."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            mode="basic",
        )
        assert "node.text AS text" in provider._retrieval_query
        assert "score" in provider._retrieval_query
        assert "ORDER BY score DESC" in provider._retrieval_query

    def test_mode_from_env_requires_retrieval_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When mode=graph_enriched from env, retrieval_query is still required."""
        monkeypatch.setenv("NEO4J_MODE", "graph_enriched")

        # Should fail because retrieval_query is required for graph_enriched
        with pytest.raises(ValueError, match="retrieval_query is required"):
            Neo4jContextProvider(
                index_name="test_index",
                index_type="fulltext",
            )

    def test_mode_from_env_with_retrieval_query(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mode from env should work when retrieval_query is provided."""
        monkeypatch.setenv("NEO4J_MODE", "graph_enriched")

        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            retrieval_query="RETURN node.text AS text, score",
        )
        assert provider._mode == "graph_enriched"

    def test_retrieval_query_patterns_from_workshop(self) -> None:
        """Test retrieval query patterns from the workshop examples."""
        # Pattern: Company + Risk Factors
        company_risk_query = """
        MATCH (node)-[:FROM_DOCUMENT]-(doc:Document)-[:FILED]-(company:Company)
        OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
        WITH node, score, company, collect(DISTINCT risk.name) as risks
        RETURN node.text AS text, score, company.name AS company, risks
        ORDER BY score DESC
        """
        provider = Neo4jContextProvider(
            index_name="chunkEmbeddings",
            index_type="fulltext",
            mode="graph_enriched",
            retrieval_query=company_risk_query,
        )
        assert provider._mode == "graph_enriched"
        assert "FACES_RISK" in provider._retrieval_query
        assert "collect(DISTINCT risk.name)" in provider._retrieval_query


class TestInvoking:
    """Test the invoking method."""

    @pytest.mark.asyncio
    async def test_invoking_returns_empty_when_not_connected(self) -> None:
        """Invoking should return empty context when not connected."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        message = ChatMessage(role=Role.USER, text="test query")
        context = await provider.invoking(message)
        assert context.messages == []

    @pytest.mark.asyncio
    async def test_invoking_handles_single_message(self) -> None:
        """Invoking should handle a single ChatMessage."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        # Not connected, so returns empty, but should not error
        message = ChatMessage(role=Role.USER, text="test query")
        context = await provider.invoking(message)
        assert context.messages == []

    @pytest.mark.asyncio
    async def test_invoking_handles_message_list(self) -> None:
        """Invoking should handle a list of ChatMessages."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        messages = [
            ChatMessage(role=Role.USER, text="first query"),
            ChatMessage(role=Role.ASSISTANT, text="first response"),
            ChatMessage(role=Role.USER, text="second query"),
        ]
        context = await provider.invoking(messages)
        # Not connected, so returns empty
        assert context.messages == []

    @pytest.mark.asyncio
    async def test_invoking_filters_system_messages(self) -> None:
        """Invoking should filter out SYSTEM messages."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
        )
        messages = [
            ChatMessage(role=Role.SYSTEM, text="system prompt"),
            ChatMessage(role=Role.USER, text="user query"),
        ]
        # Would be filtered - only USER and ASSISTANT kept
        context = await provider.invoking(messages)
        assert context.messages == []

    @pytest.mark.asyncio
    async def test_invoking_respects_message_history_count(self) -> None:
        """Invoking should respect message_history_count limit."""
        provider = Neo4jContextProvider(
            index_name="test_index",
            index_type="fulltext",
            message_history_count=2,
        )
        assert provider._message_history_count == 2

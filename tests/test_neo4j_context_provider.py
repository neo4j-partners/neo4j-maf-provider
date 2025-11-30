"""
Tests for Neo4j Context Provider.

These tests verify the context provider implementation at each phase.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_framework import ChatMessage, Context

from neo4j_context_provider import Neo4jContextProvider


class TestStaticContextProvider:
    """Test that provider returns expected context without Neo4j connection."""

    @pytest.mark.asyncio
    async def test_invoking_returns_context(self):
        """Test that invoking returns a Context object."""
        provider = Neo4jContextProvider()
        messages = [ChatMessage(role="user", text="Tell me about Apple")]

        context = await provider.invoking(messages)

        assert isinstance(context, Context)

    @pytest.mark.asyncio
    async def test_invoking_returns_instructions(self):
        """Test that invoking returns non-empty instructions."""
        provider = Neo4jContextProvider()
        messages = [ChatMessage(role="user", text="Hello")]

        context = await provider.invoking(messages)

        assert context.instructions is not None
        assert len(context.instructions) > 0
        assert "Knowledge Graph" in context.instructions

    @pytest.mark.asyncio
    async def test_invoking_with_single_message(self):
        """Test that invoking works with a single ChatMessage (not list)."""
        provider = Neo4jContextProvider()
        message = ChatMessage(role="user", text="Test message")

        context = await provider.invoking(message)

        assert isinstance(context, Context)

    @pytest.mark.asyncio
    async def test_context_manager_protocol(self):
        """Test that provider works as async context manager."""
        async with Neo4jContextProvider() as provider:
            assert provider is not None
            context = await provider.invoking([ChatMessage(role="user", text="Test")])
            assert isinstance(context, Context)


class TestClientLifecycle:
    """Test Neo4jClient composition and lifecycle management."""

    @pytest.mark.asyncio
    async def test_provider_without_client(self):
        """Test that provider works without a Neo4j client."""
        provider = Neo4jContextProvider(neo4j_client=None)

        async with provider:
            assert not provider.is_connected
            context = await provider.invoking([ChatMessage(role="user", text="Test")])
            assert isinstance(context, Context)

    @pytest.mark.asyncio
    async def test_provider_with_mock_client(self):
        """Test that provider manages mock client lifecycle correctly."""
        # Create a mock Neo4jClient
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        # Before entering context
        assert not provider.is_connected

        async with provider:
            # Should have called __aenter__ on the client
            mock_client.__aenter__.assert_called_once()
            assert provider.is_connected

            # invoking should still work
            context = await provider.invoking([ChatMessage(role="user", text="Test")])
            assert isinstance(context, Context)

        # After exiting context
        mock_client.__aexit__.assert_called_once()
        assert not provider.is_connected

    @pytest.mark.asyncio
    async def test_client_context_cleanup_on_exception(self):
        """Test that client context is cleaned up even if exception occurs."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        with pytest.raises(ValueError):
            async with provider:
                assert provider.is_connected
                raise ValueError("Test exception")

        # Should still have cleaned up
        mock_client.__aexit__.assert_called_once()
        assert not provider.is_connected

    @pytest.mark.asyncio
    async def test_is_connected_property(self):
        """Test is_connected property reflects actual connection state."""
        provider = Neo4jContextProvider(neo4j_client=None)
        assert not provider.is_connected

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        provider_with_client = Neo4jContextProvider(neo4j_client=mock_client)
        assert not provider_with_client.is_connected

        async with provider_with_client:
            assert provider_with_client.is_connected

        assert not provider_with_client.is_connected


class TestEntityExtraction:
    """Test entity extraction from messages."""

    def test_extract_potential_entities_basic(self):
        """Test basic entity extraction."""
        provider = Neo4jContextProvider()
        entities = provider._extract_potential_entities("Tell me about Apple")

        assert "Apple" in entities
        assert "Tell" not in entities  # stopword
        assert "me" not in entities  # stopword
        assert "about" not in entities  # stopword

    def test_extract_potential_entities_multiple(self):
        """Test extraction of multiple entities."""
        provider = Neo4jContextProvider()
        entities = provider._extract_potential_entities(
            "What is the relationship between Microsoft and Google?"
        )

        assert "Microsoft" in entities
        assert "Google" in entities
        assert "relationship" in entities

    def test_extract_potential_entities_deduplication(self):
        """Test that duplicate entities are removed."""
        provider = Neo4jContextProvider()
        entities = provider._extract_potential_entities("Apple makes Apple products")

        # Should only have one "Apple" (case-insensitive dedup)
        apple_count = sum(1 for e in entities if e.lower() == "apple")
        assert apple_count == 1

    def test_extract_potential_entities_empty(self):
        """Test extraction from empty string."""
        provider = Neo4jContextProvider()
        entities = provider._extract_potential_entities("")

        assert entities == []

    def test_extract_potential_entities_only_stopwords(self):
        """Test extraction when message contains only stopwords."""
        provider = Neo4jContextProvider()
        entities = provider._extract_potential_entities("The is a to of")

        assert entities == []

    def test_extract_query_text_single_message(self):
        """Test text extraction from single message."""
        provider = Neo4jContextProvider()
        message = ChatMessage(role="user", text="Tell me about Apple")

        text = provider._extract_query_text(message)

        assert text == "Tell me about Apple"

    def test_extract_query_text_multiple_messages(self):
        """Test text extraction from multiple messages."""
        provider = Neo4jContextProvider()
        messages = [
            ChatMessage(role="user", text="Tell me about Apple"),
            ChatMessage(role="assistant", text="Apple is a company"),
            ChatMessage(role="user", text="What about Microsoft?"),
        ]

        text = provider._extract_query_text(messages)

        assert "Apple" in text
        assert "Microsoft" in text


class TestRelationshipFormatting:
    """Test relationship formatting."""

    def test_format_relationships_basic(self):
        """Test basic relationship formatting."""
        provider = Neo4jContextProvider()
        relationships = [
            {
                "source": "Apple",
                "source_type": "Company",
                "relationship": "FOUNDED_BY",
                "target": "Steve Jobs",
                "target_type": "Executive",
            }
        ]

        formatted = provider._format_relationships(relationships)

        assert "Knowledge Graph Context" in formatted
        assert "Apple (Company)" in formatted
        assert "FOUNDED_BY" in formatted
        assert "Steve Jobs (Executive)" in formatted

    def test_format_relationships_multiple(self):
        """Test formatting multiple relationships."""
        provider = Neo4jContextProvider()
        relationships = [
            {
                "source": "Apple",
                "source_type": "Company",
                "relationship": "MAKES",
                "target": "iPhone",
                "target_type": "Product",
            },
            {
                "source": "Apple",
                "source_type": "Company",
                "relationship": "FOUNDED_BY",
                "target": "Steve Jobs",
                "target_type": "Executive",
            },
        ]

        formatted = provider._format_relationships(relationships)

        assert "iPhone" in formatted
        assert "Steve Jobs" in formatted
        assert formatted.count("--[") == 2  # Two relationships

    def test_format_relationships_empty(self):
        """Test formatting empty relationships list."""
        provider = Neo4jContextProvider()
        formatted = provider._format_relationships([])

        assert formatted == ""

    def test_format_relationships_missing_type(self):
        """Test formatting when type is missing."""
        provider = Neo4jContextProvider()
        relationships = [
            {
                "source": "Apple",
                "source_type": "",
                "relationship": "RELATED_TO",
                "target": "Technology",
                "target_type": "",
            }
        ]

        formatted = provider._format_relationships(relationships)

        # Should not include empty parentheses
        assert "Apple --[RELATED_TO]--> Technology" in formatted
        assert "()" not in formatted


class TestSingleHopRetrieval:
    """Test single-hop relationship retrieval with Neo4j."""

    @pytest.mark.asyncio
    async def test_invoking_with_relationships(self):
        """Test invoking returns relationships from Neo4j."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_entity_relationships = AsyncMock(
            return_value=[
                {
                    "source": "Apple",
                    "source_type": "Company",
                    "relationship": "MAKES",
                    "target": "iPhone",
                    "target_type": "Product",
                }
            ]
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        assert context.instructions is not None
        assert "Apple" in context.instructions
        assert "iPhone" in context.instructions

    @pytest.mark.asyncio
    async def test_invoking_no_relationships_found(self):
        """Test invoking when no relationships are found."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_entity_relationships = AsyncMock(return_value=[])

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about UnknownEntity123")]
            )

        # Should return empty context when no relationships found
        assert context.instructions is None or context.instructions == ""

    @pytest.mark.asyncio
    async def test_invoking_deduplicates_relationships(self):
        """Test that duplicate relationships are removed."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Return same relationship for different entity queries
        mock_client.get_entity_relationships = AsyncMock(
            return_value=[
                {
                    "source": "Apple",
                    "source_type": "Company",
                    "relationship": "MAKES",
                    "target": "iPhone",
                    "target_type": "Product",
                }
            ]
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        async with provider:
            # Query mentions Apple twice
            context = await provider.invoking(
                [ChatMessage(role="user", text="Apple makes Apple products")]
            )

        # Should only have one instance of the relationship
        assert context.instructions is not None
        assert context.instructions.count("Apple (Company)") == 1

    @pytest.mark.asyncio
    async def test_invoking_respects_max_relationships(self):
        """Test that max_relationships limit is respected."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Return many relationships
        mock_client.get_entity_relationships = AsyncMock(
            return_value=[
                {
                    "source": f"Entity{i}",
                    "source_type": "Type",
                    "relationship": "REL",
                    "target": f"Target{i}",
                    "target_type": "Type",
                }
                for i in range(20)
            ]
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_relationships=5)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Query")]
            )

        # Should have at most 5 relationships
        assert context.instructions is not None
        assert context.instructions.count("--[REL]-->") <= 5

    @pytest.mark.asyncio
    async def test_invoking_handles_query_error(self):
        """Test that errors from Neo4j are handled gracefully."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get_entity_relationships = AsyncMock(
            side_effect=Exception("Database error")
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client)

        async with provider:
            # Should not raise, just return empty context
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Should return empty context on error
        assert context.instructions is None or context.instructions == ""

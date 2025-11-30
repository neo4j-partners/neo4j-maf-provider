"""
Tests for multi-hop path traversal in Neo4j Context Provider.

These tests verify variable-length path queries and path formatting.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_framework import ChatMessage, Context

from neo4j_context_provider import Neo4jContextProvider


class TestMaxHopsConfiguration:
    """Test max_hops parameter validation and configuration."""

    def test_default_max_hops_is_one(self):
        """Test that default max_hops is 1 (single-hop behavior)."""
        provider = Neo4jContextProvider()
        assert provider._max_hops == 1

    def test_max_hops_can_be_configured(self):
        """Test that max_hops can be set to valid values."""
        provider = Neo4jContextProvider(max_hops=2)
        assert provider._max_hops == 2

        provider = Neo4jContextProvider(max_hops=3)
        assert provider._max_hops == 3

    def test_max_hops_minimum_validation(self):
        """Test that max_hops below 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_hops must be between 1 and 5"):
            Neo4jContextProvider(max_hops=0)

        with pytest.raises(ValueError, match="max_hops must be between 1 and 5"):
            Neo4jContextProvider(max_hops=-1)

    def test_max_hops_maximum_validation(self):
        """Test that max_hops above 5 raises ValueError."""
        with pytest.raises(ValueError, match="max_hops must be between 1 and 5"):
            Neo4jContextProvider(max_hops=6)

        with pytest.raises(ValueError, match="max_hops must be between 1 and 5"):
            Neo4jContextProvider(max_hops=10)


class TestPathFormatting:
    """Test formatting of multi-hop paths."""

    def test_format_paths_single_hop(self):
        """Test formatting a single-hop path (2 nodes, 1 relationship)."""
        provider = Neo4jContextProvider(max_hops=2)
        paths = [
            {
                "path_nodes": [
                    {"name": "Apple", "type": "Company"},
                    {"name": "iPhone", "type": "Product"},
                ],
                "path_rels": ["MAKES"],
            }
        ]

        formatted = provider._format_paths(paths)

        assert "Knowledge Graph Context" in formatted
        assert "Apple (Company)" in formatted
        assert "--[MAKES]-->" in formatted
        assert "iPhone (Product)" in formatted

    def test_format_paths_two_hop(self):
        """Test formatting a two-hop path (3 nodes, 2 relationships)."""
        provider = Neo4jContextProvider(max_hops=2)
        paths = [
            {
                "path_nodes": [
                    {"name": "Apple", "type": "Company"},
                    {"name": "Tim Cook", "type": "Executive"},
                    {"name": "Stanford", "type": "University"},
                ],
                "path_rels": ["LED_BY", "GRADUATED_FROM"],
            }
        ]

        formatted = provider._format_paths(paths)

        assert "Apple (Company)" in formatted
        assert "--[LED_BY]-->" in formatted
        assert "Tim Cook (Executive)" in formatted
        assert "--[GRADUATED_FROM]-->" in formatted
        assert "Stanford (University)" in formatted

    def test_format_paths_multiple_paths(self):
        """Test formatting multiple paths."""
        provider = Neo4jContextProvider(max_hops=2)
        paths = [
            {
                "path_nodes": [
                    {"name": "Apple", "type": "Company"},
                    {"name": "iPhone", "type": "Product"},
                ],
                "path_rels": ["MAKES"],
            },
            {
                "path_nodes": [
                    {"name": "Apple", "type": "Company"},
                    {"name": "Tim Cook", "type": "Executive"},
                ],
                "path_rels": ["LED_BY"],
            },
        ]

        formatted = provider._format_paths(paths)

        assert formatted.count("Apple (Company)") == 2
        assert "iPhone" in formatted
        assert "Tim Cook" in formatted

    def test_format_paths_empty(self):
        """Test formatting empty paths list."""
        provider = Neo4jContextProvider(max_hops=2)
        formatted = provider._format_paths([])

        assert formatted == ""

    def test_format_paths_missing_type(self):
        """Test formatting when node type is missing."""
        provider = Neo4jContextProvider(max_hops=2)
        paths = [
            {
                "path_nodes": [
                    {"name": "Apple", "type": ""},
                    {"name": "Technology", "type": ""},
                ],
                "path_rels": ["RELATED_TO"],
            }
        ]

        formatted = provider._format_paths(paths)

        # Should not include empty parentheses
        assert "Apple --[RELATED_TO]--> Technology" in formatted
        assert "()" not in formatted

    def test_format_paths_three_hop(self):
        """Test formatting a three-hop path (4 nodes, 3 relationships)."""
        provider = Neo4jContextProvider(max_hops=3)
        paths = [
            {
                "path_nodes": [
                    {"name": "Apple", "type": "Company"},
                    {"name": "Tim Cook", "type": "Executive"},
                    {"name": "Stanford", "type": "University"},
                    {"name": "California", "type": "Location"},
                ],
                "path_rels": ["LED_BY", "GRADUATED_FROM", "LOCATED_IN"],
            }
        ]

        formatted = provider._format_paths(paths)

        assert "Apple (Company)" in formatted
        assert "Tim Cook (Executive)" in formatted
        assert "Stanford (University)" in formatted
        assert "California (Location)" in formatted
        assert formatted.count("-->") == 3


class TestMultiHopRetrieval:
    """Test multi-hop path retrieval with Neo4j."""

    @pytest.mark.asyncio
    async def test_invoking_uses_multi_hop_when_configured(self):
        """Test that invoking uses multi-hop when max_hops > 1."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.execute_query = AsyncMock(
            return_value=[
                {
                    "path_nodes": [
                        {"name": "Apple", "type": "Company"},
                        {"name": "Tim Cook", "type": "Executive"},
                        {"name": "Stanford", "type": "University"},
                    ],
                    "path_rels": ["LED_BY", "GRADUATED_FROM"],
                }
            ]
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=2)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Should have called execute_query (not get_entity_relationships)
        mock_client.execute_query.assert_called()
        assert context.instructions is not None
        assert "Apple" in context.instructions
        assert "Tim Cook" in context.instructions
        assert "Stanford" in context.instructions

    @pytest.mark.asyncio
    async def test_invoking_uses_single_hop_by_default(self):
        """Test that invoking uses single-hop when max_hops = 1."""
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

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=1)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Should have called get_entity_relationships (not execute_query)
        mock_client.get_entity_relationships.assert_called()
        assert context.instructions is not None
        assert "Apple" in context.instructions

    @pytest.mark.asyncio
    async def test_multi_hop_no_paths_found(self):
        """Test multi-hop when no paths are found."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.execute_query = AsyncMock(return_value=[])

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=2)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about UnknownEntity")]
            )

        # Should return empty context when no paths found
        assert context.instructions is None or context.instructions == ""

    @pytest.mark.asyncio
    async def test_multi_hop_deduplicates_paths(self):
        """Test that duplicate paths are removed."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Return same path multiple times
        mock_client.execute_query = AsyncMock(
            return_value=[
                {
                    "path_nodes": [
                        {"name": "Apple", "type": "Company"},
                        {"name": "iPhone", "type": "Product"},
                    ],
                    "path_rels": ["MAKES"],
                },
                {
                    "path_nodes": [
                        {"name": "Apple", "type": "Company"},
                        {"name": "iPhone", "type": "Product"},
                    ],
                    "path_rels": ["MAKES"],
                },
            ]
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=2)

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Should only have one instance of the path
        assert context.instructions is not None
        assert context.instructions.count("Apple (Company)") == 1

    @pytest.mark.asyncio
    async def test_multi_hop_respects_max_relationships(self):
        """Test that max_relationships limit is respected for paths."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Return many paths
        mock_client.execute_query = AsyncMock(
            return_value=[
                {
                    "path_nodes": [
                        {"name": f"Entity{i}", "type": "Type"},
                        {"name": f"Target{i}", "type": "Type"},
                    ],
                    "path_rels": ["REL"],
                }
                for i in range(20)
            ]
        )

        provider = Neo4jContextProvider(
            neo4j_client=mock_client,
            max_hops=2,
            max_relationships=5,
        )

        async with provider:
            context = await provider.invoking(
                [ChatMessage(role="user", text="Query")]
            )

        # Should have at most 5 paths
        assert context.instructions is not None
        assert context.instructions.count("--[REL]-->") <= 5

    @pytest.mark.asyncio
    async def test_multi_hop_handles_query_error(self):
        """Test that errors from Neo4j are handled gracefully."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.execute_query = AsyncMock(
            side_effect=Exception("Database error")
        )

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=2)

        async with provider:
            # Should not raise, just return empty context
            context = await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Should return empty context on error
        assert context.instructions is None or context.instructions == ""

    @pytest.mark.asyncio
    async def test_cypher_query_includes_max_hops(self):
        """Test that the Cypher query uses the configured max_hops value."""
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.execute_query = AsyncMock(return_value=[])

        provider = Neo4jContextProvider(neo4j_client=mock_client, max_hops=3)

        async with provider:
            await provider.invoking(
                [ChatMessage(role="user", text="Tell me about Apple")]
            )

        # Verify the query includes the correct path length
        call_args = mock_client.execute_query.call_args
        query = call_args[0][0]
        assert "[*1..3]" in query

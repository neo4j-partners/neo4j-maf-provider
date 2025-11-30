"""
Neo4j Context Provider for Microsoft Agent Framework.

This module provides a context provider that enhances agent responses with
knowledge graph data from Neo4j, supporting relationship retrieval,
multi-hop traversal, and path-based queries.
"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableSequence
from types import TracebackType
from typing import Any

from agent_framework import ChatMessage, Context, ContextProvider

from logging_config import configure_logging
from neo4j_client import Neo4jClient

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))

# Common stopwords to filter out during entity extraction
STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "and", "but", "if", "or",
    "because", "until", "while", "although", "though", "after", "before",
    "what", "which", "who", "whom", "this", "that", "these", "those", "am",
    "about", "tell", "me", "show", "find", "get", "give", "know", "think",
    "want", "see", "look", "make", "go", "come", "take", "use", "try",
    "also", "well", "just", "even", "back", "any", "our", "out", "up",
    "i", "you", "he", "she", "it", "we", "they", "my", "your", "his", "her",
    "its", "their", "us", "them", "him", "yourself", "myself", "itself",
})


class Neo4jContextProvider(ContextProvider):
    """
    Context provider that retrieves knowledge graph context from Neo4j.

    This provider enhances agent responses by injecting relevant graph data
    (entities, relationships, paths) into the agent's context before each
    LLM invocation.

    Uses composition with Neo4jClient for database operations.

    Usage:
        from neo4j_client import Neo4jClient, Neo4jConfig

        config = Neo4jConfig()
        neo4j_client = Neo4jClient(config)

        async with Neo4jContextProvider(neo4j_client=neo4j_client) as provider:
            async with ChatAgent(
                chat_client=client,
                context_providers=provider,
            ) as agent:
                response = await agent.run("Tell me about Apple")
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient | None = None,
        max_relationships: int = 10,
        max_hops: int = 1,
    ) -> None:
        """
        Initialize the context provider.

        Args:
            neo4j_client: Neo4jClient instance for database operations.
                         If None, provider returns static context only.
            max_relationships: Maximum number of relationships to retrieve per query.
            max_hops: Maximum path length for traversal. 1 = single-hop,
                     2+ = multi-hop using variable-length paths.
        """
        if max_hops < 1 or max_hops > 5:
            raise ValueError("max_hops must be between 1 and 5")
        self._neo4j_client = neo4j_client
        self._owns_client_context = False
        self._max_relationships = max_relationships
        self._max_hops = max_hops

    async def __aenter__(self) -> Self:
        """Enter async context and connect to Neo4j if client provided."""
        if self._neo4j_client is not None:
            await self._neo4j_client.__aenter__()
            self._owns_client_context = True
            logger.info("Neo4jContextProvider connected to Neo4j")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit async context and close Neo4j connection."""
        if self._neo4j_client is not None and self._owns_client_context:
            await self._neo4j_client.__aexit__(exc_type, exc_val, exc_tb)
            self._owns_client_context = False
            logger.info("Neo4jContextProvider disconnected from Neo4j")

    @property
    def is_connected(self) -> bool:
        """Check if the provider is connected to Neo4j."""
        return self._neo4j_client is not None and self._owns_client_context

    def _extract_query_text(
        self,
        messages: ChatMessage | MutableSequence[ChatMessage],
    ) -> str:
        """Extract text content from messages for entity extraction."""
        if isinstance(messages, ChatMessage):
            return messages.text or ""

        # Get text from all messages, focusing on user messages
        texts = []
        for msg in messages:
            if msg.text:
                texts.append(msg.text)
        return " ".join(texts)

    def _extract_potential_entities(self, text: str) -> list[str]:
        """
        Extract potential entity names from text using simple keyword extraction.

        This is a basic approach that:
        1. Splits text into words
        2. Filters out stopwords
        3. Keeps words that might be entity names (capitalized or longer words)

        Args:
            text: The text to extract entities from.

        Returns:
            List of potential entity names, deduplicated and ordered.
        """
        if not text:
            return []

        # Split on whitespace and punctuation, keep alphanumeric
        words = []
        current_word = []
        for char in text:
            if char.isalnum() or char == "'":
                current_word.append(char)
            else:
                if current_word:
                    words.append("".join(current_word))
                    current_word = []
        if current_word:
            words.append("".join(current_word))

        # Filter and deduplicate
        seen = set()
        entities = []
        for word in words:
            word_lower = word.lower()
            # Skip stopwords and very short words
            if word_lower in STOPWORDS or len(word) < 2:
                continue
            # Skip if already seen (case-insensitive)
            if word_lower in seen:
                continue
            seen.add(word_lower)
            # Keep the original casing for the entity
            entities.append(word)

        return entities

    def _format_relationships(
        self,
        relationships: list[dict[str, str]],
    ) -> str:
        """
        Format relationship data as context instructions.

        Args:
            relationships: List of relationship dicts from Neo4jClient.

        Returns:
            Formatted string for context instructions.
        """
        if not relationships:
            return ""

        lines = ["## Knowledge Graph Context", ""]
        lines.append("The following relationships were found in the knowledge graph:")
        lines.append("")

        for rel in relationships:
            source = rel.get("source", "Unknown")
            source_type = rel.get("source_type", "")
            relationship = rel.get("relationship", "RELATED_TO")
            target = rel.get("target", "Unknown")
            target_type = rel.get("target_type", "")

            # Format: "Apple (Company) --[FOUNDED_BY]--> Steve Jobs (Executive)"
            source_label = f"{source} ({source_type})" if source_type else source
            target_label = f"{target} ({target_type})" if target_type else target
            lines.append(f"- {source_label} --[{relationship}]--> {target_label}")

        return "\n".join(lines)

    async def _get_multi_hop_paths(
        self,
        entity_name: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Get multi-hop paths from an entity using variable-length path patterns.

        Uses execute_query() with Cypher variable-length paths to find
        indirect relationships up to max_hops away.

        Args:
            entity_name: The entity name to search for (case-insensitive contains).
            limit: Maximum number of paths to return.

        Returns:
            List of path dicts with 'path_nodes' and 'path_rels' keys.
        """
        if self._neo4j_client is None:
            return []

        # Build query with validated max_hops (already validated in __init__)
        # Note: Cypher doesn't support parameterized path lengths, so we use f-string
        # with the validated integer value
        query = f"""
        MATCH path = (source)-[*1..{self._max_hops}]->(target)
        WHERE toLower(source.name) CONTAINS toLower($entity_name)
          AND source.name IS NOT NULL
          AND target.name IS NOT NULL
          AND NOT source:Document AND NOT source:Chunk
          AND NOT target:Document AND NOT target:Chunk
        RETURN
            [n IN nodes(path) | {{
                name: n.name,
                type: [l IN labels(n) WHERE NOT l STARTS WITH '__'][0]
            }}] AS path_nodes,
            [r IN relationships(path) | type(r)] AS path_rels
        LIMIT $limit
        """

        return await self._neo4j_client.execute_query(
            query,
            {"entity_name": entity_name, "limit": limit},
        )

    def _format_paths(
        self,
        paths: list[dict[str, Any]],
    ) -> str:
        """
        Format multi-hop path data as context instructions.

        Args:
            paths: List of path dicts with 'path_nodes' and 'path_rels' keys.

        Returns:
            Formatted string showing reasoning chains.
        """
        if not paths:
            return ""

        lines = ["## Knowledge Graph Context", ""]
        lines.append("The following paths were found in the knowledge graph:")
        lines.append("")

        for path in paths:
            path_nodes = path.get("path_nodes", [])
            path_rels = path.get("path_rels", [])

            if not path_nodes:
                continue

            # Format: "Node1 (Type1) --[REL1]--> Node2 (Type2) --[REL2]--> Node3 (Type3)"
            parts = []
            for i, node in enumerate(path_nodes):
                name = node.get("name", "Unknown")
                node_type = node.get("type", "")
                node_label = f"{name} ({node_type})" if node_type else name
                parts.append(node_label)

                # Add relationship arrow if not the last node
                if i < len(path_rels):
                    rel = path_rels[i]
                    parts.append(f"--[{rel}]-->")

            lines.append(f"- {' '.join(parts)}")

        return "\n".join(lines)

    async def invoking(
        self,
        messages: ChatMessage | MutableSequence[ChatMessage],
        **kwargs: Any,
    ) -> Context:
        """
        Called before each LLM invocation to provide graph context.

        Extracts potential entity names from the messages and queries Neo4j
        for relationships involving those entities.

        Args:
            messages: The messages being sent to the LLM.
            **kwargs: Additional keyword arguments.

        Returns:
            Context with instructions derived from Neo4j graph data.
        """
        # If not connected to Neo4j, return static context
        if not self.is_connected or self._neo4j_client is None:
            instructions = (
                "## Knowledge Graph Context\n"
                "This agent has access to a knowledge graph with information about "
                "companies, executives, products, and their relationships."
            )
            return Context(instructions=instructions)

        # Extract potential entities from the query
        query_text = self._extract_query_text(messages)
        potential_entities = self._extract_potential_entities(query_text)

        if not potential_entities:
            logger.debug("No potential entities extracted from query")
            return Context()

        logger.debug(f"Extracted potential entities: {potential_entities}")

        # Use multi-hop traversal when max_hops > 1, otherwise single-hop
        if self._max_hops > 1:
            return await self._invoking_multi_hop(potential_entities)
        else:
            return await self._invoking_single_hop(potential_entities)

    async def _invoking_single_hop(
        self,
        potential_entities: list[str],
    ) -> Context:
        """
        Query single-hop relationships using get_entity_relationships().

        Args:
            potential_entities: List of entity names to query.

        Returns:
            Context with formatted single-hop relationships.
        """
        all_relationships: list[dict[str, str]] = []
        seen_relationships: set[str] = set()

        for entity in potential_entities:
            if len(all_relationships) >= self._max_relationships:
                break

            try:
                relationships = await self._neo4j_client.get_entity_relationships(
                    entity_name=entity,
                    limit=self._max_relationships - len(all_relationships),
                )

                # Deduplicate relationships and enforce limit
                for rel in relationships:
                    if len(all_relationships) >= self._max_relationships:
                        break
                    rel_key = f"{rel['source']}|{rel['relationship']}|{rel['target']}"
                    if rel_key not in seen_relationships:
                        seen_relationships.add(rel_key)
                        all_relationships.append(rel)

            except Exception as e:
                logger.warning(f"Error querying relationships for '{entity}': {e}")
                continue

        if not all_relationships:
            logger.debug("No relationships found for extracted entities")
            return Context()

        logger.info(f"Found {len(all_relationships)} relationships for context")

        # Format relationships as context
        instructions = self._format_relationships(all_relationships)
        return Context(instructions=instructions)

    async def _invoking_multi_hop(
        self,
        potential_entities: list[str],
    ) -> Context:
        """
        Query multi-hop paths using execute_query() with variable-length patterns.

        Args:
            potential_entities: List of entity names to query.

        Returns:
            Context with formatted multi-hop paths.
        """
        all_paths: list[dict[str, Any]] = []
        seen_paths: set[str] = set()

        for entity in potential_entities:
            if len(all_paths) >= self._max_relationships:
                break

            try:
                paths = await self._get_multi_hop_paths(
                    entity_name=entity,
                    limit=self._max_relationships - len(all_paths),
                )

                # Deduplicate paths by their signature and enforce limit
                for path in paths:
                    if len(all_paths) >= self._max_relationships:
                        break
                    # Create path signature from nodes and relationships
                    nodes = path.get("path_nodes", [])
                    rels = path.get("path_rels", [])
                    node_names = [n.get("name", "") for n in nodes]
                    path_key = "|".join(node_names) + "|" + "|".join(rels)
                    if path_key not in seen_paths:
                        seen_paths.add(path_key)
                        all_paths.append(path)

            except Exception as e:
                logger.warning(f"Error querying paths for '{entity}': {e}")
                continue

        if not all_paths:
            logger.debug("No paths found for extracted entities")
            return Context()

        logger.info(f"Found {len(all_paths)} paths for context")

        # Format paths as context
        instructions = self._format_paths(all_paths)
        return Context(instructions=instructions)

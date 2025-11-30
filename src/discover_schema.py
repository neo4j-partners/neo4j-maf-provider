"""
Neo4j Schema Discovery Script.

Discovers the graph schema and finds example entities/relationships
that can be used for testing the context provider.

Run with: uv run python src/discover_schema.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from api.neo4j_utils import list_entities_by_type
from neo4j_client import Neo4jClient, Neo4jSettings
from util import get_env_file_path

# Entity labels to look for when discovering schema
ALLOWED_ENTITY_LABELS = frozenset({
    "Company",
    "Executive",
    "Product",
    "FinancialMetric",
    "RiskFactor",
    "StockType",
    "Transaction",
    "TimePeriod",
})


async def discover_schema() -> None:
    """Discover and print the Neo4j schema with examples."""
    # Load environment
    env_path = get_env_file_path()
    if env_path:
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}\n")

    config = Neo4jSettings()

    if not config.is_configured:
        print("ERROR: Neo4j not configured.")
        print("Required environment variables: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        return

    print(f"Connecting to Neo4j at: {config.uri}")
    print("=" * 60)

    async with Neo4jClient(config) as client:
        # Get schema
        schema = await client.get_schema()

        print("\n## NODE LABELS")
        print("-" * 40)
        for label in sorted(schema.node_labels):
            props = schema.node_properties.get(label, [])
            print(f"  :{label}")
            if props:
                print(f"    Properties: {', '.join(sorted(props)[:5])}")

        print("\n## RELATIONSHIP TYPES")
        print("-" * 40)
        for rel_type in sorted(schema.relationship_types):
            props = schema.relationship_properties.get(rel_type, [])
            print(f"  -[:{rel_type}]->")
            if props:
                print(f"    Properties: {', '.join(sorted(props)[:5])}")

        # Find example entities
        print("\n## EXAMPLE ENTITIES (for testing)")
        print("-" * 40)

        # Try allowed entity types that exist in the schema
        for entity_type in sorted(ALLOWED_ENTITY_LABELS):
            if entity_type in schema.node_labels:
                try:
                    entities = await list_entities_by_type(client, entity_type, limit=5)
                    if entities:
                        print(f"\n  {entity_type}:")
                        for e in entities:
                            print(f"    - {e['name']}")
                except Exception as e:
                    print(f"\n  {entity_type}: Error - {e}")

        # Find example relationships
        print("\n## EXAMPLE RELATIONSHIPS (for testing)")
        print("-" * 40)

        # Query for some actual relationships
        example_query = """
        MATCH (source)-[r]->(target)
        WHERE source.name IS NOT NULL
          AND target.name IS NOT NULL
          AND NOT source:Document AND NOT source:Chunk
          AND NOT target:Document AND NOT target:Chunk
        RETURN
            labels(source)[0] AS source_type,
            source.name AS source_name,
            type(r) AS relationship,
            labels(target)[0] AS target_type,
            target.name AS target_name
        LIMIT 10
        """

        try:
            results = await client.execute_query(example_query)
            for r in results:
                src = f"{r['source_name']} ({r['source_type']})"
                tgt = f"{r['target_name']} ({r['target_type']})"
                rel = r['relationship']
                print(f"  {src} --[{rel}]--> {tgt}")
        except Exception as e:
            print(f"  Error querying relationships: {e}")

        # Find good test queries
        print("\n## SUGGESTED TEST QUERIES")
        print("-" * 40)

        # Find entities with most relationships
        connected_query = """
        MATCH (n)-[r]-()
        WHERE n.name IS NOT NULL
          AND NOT n:Document AND NOT n:Chunk
        WITH n, count(r) AS rel_count, labels(n)[0] AS label
        ORDER BY rel_count DESC
        LIMIT 5
        RETURN n.name AS name, label, rel_count
        """

        try:
            results = await client.execute_query(connected_query)
            print("\n  Most connected entities (good for testing):")
            for r in results:
                name = r['name']
                label = r['label']
                count = r['rel_count']
                print(f"    - '{name}' ({label}) - {count} relationships")
                print(f"      Query: \"Tell me about {name}\"")
        except Exception as e:
            print(f"  Error finding connected entities: {e}")

        print("\n" + "=" * 60)
        print("Schema discovery complete!")


def main() -> None:
    """Entry point."""
    asyncio.run(discover_schema())


if __name__ == "__main__":
    main()

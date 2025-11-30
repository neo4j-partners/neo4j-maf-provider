"""
Explore the Aircraft Neo4j database to understand its schema and data.

This script investigates the AIRCRAFT_NEO4J database to:
1. Discover node labels and relationship types
2. Find example data for demo purposes
3. Identify opportunities for fulltext and vector search indexes
4. Propose retrieval query patterns for graph-enriched mode

Run with: uv run python src/explore_aircraft_db.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from util import get_env_file_path


async def explore_aircraft_database() -> None:
    """Explore the Aircraft Neo4j database."""
    # Load environment
    env_path = get_env_file_path()
    if env_path:
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}\n")

    # Get aircraft database credentials
    uri = os.getenv("AIRCRAFT_NEO4J_URI")
    username = os.getenv("AIRCRAFT_NEO4J_USERNAME")
    password = os.getenv("AIRCRAFT_NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("ERROR: Aircraft database not configured.")
        print("Required: AIRCRAFT_NEO4J_URI, AIRCRAFT_NEO4J_USERNAME, AIRCRAFT_NEO4J_PASSWORD")
        return

    print(f"Connecting to Aircraft Neo4j at: {uri}")
    print("=" * 70)

    driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    try:
        await driver.verify_connectivity()
        print("Connected successfully!\n")

        async with driver.session() as session:
            # 1. Get node labels
            print("## 1. NODE LABELS")
            print("-" * 70)
            result = await session.run("CALL db.labels()")
            labels = [record["label"] async for record in result]
            for label in sorted(labels):
                # Get count and sample properties
                count_result = await session.run(f"MATCH (n:`{label}`) RETURN count(n) AS count")
                count_record = await count_result.single()
                count = count_record["count"] if count_record else 0

                props_result = await session.run(
                    f"MATCH (n:`{label}`) WITH n LIMIT 1 RETURN keys(n) AS props"
                )
                props_record = await props_result.single()
                props = props_record["props"] if props_record else []

                print(f"  :{label} ({count:,} nodes)")
                if props:
                    print(f"    Properties: {', '.join(sorted(props)[:8])}")

            # 2. Get relationship types
            print("\n## 2. RELATIONSHIP TYPES")
            print("-" * 70)
            result = await session.run("CALL db.relationshipTypes()")
            rel_types = [record["relationshipType"] async for record in result]
            for rel_type in sorted(rel_types):
                count_result = await session.run(
                    f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) AS count"
                )
                count_record = await count_result.single()
                count = count_record["count"] if count_record else 0
                print(f"  -[:{rel_type}]-> ({count:,} relationships)")

            # 3. Sample relationship patterns
            print("\n## 3. RELATIONSHIP PATTERNS (Source → Rel → Target)")
            print("-" * 70)
            pattern_query = """
            MATCH (source)-[r]->(target)
            WITH labels(source)[0] AS src_label, type(r) AS rel_type, labels(target)[0] AS tgt_label
            RETURN DISTINCT src_label, rel_type, tgt_label
            ORDER BY src_label, rel_type
            LIMIT 30
            """
            result = await session.run(pattern_query)
            async for record in result:
                print(f"  (:{record['src_label']}) -[:{record['rel_type']}]-> (:{record['tgt_label']})")

            # 4. Sample data from key node types
            print("\n## 4. SAMPLE DATA")
            print("-" * 70)

            # Try common aviation entity types
            for label in labels[:10]:  # Check first 10 labels
                sample_query = f"""
                MATCH (n:`{label}`)
                RETURN n
                LIMIT 3
                """
                result = await session.run(sample_query)
                records = [record async for record in result]
                if records:
                    print(f"\n  {label} samples:")
                    for record in records:
                        node = dict(record["n"])
                        # Show first few properties
                        display_props = {k: v for k, v in list(node.items())[:4]}
                        print(f"    {display_props}")

            # 5. Find text properties (candidates for fulltext search)
            print("\n## 5. TEXT PROPERTIES (Fulltext Search Candidates)")
            print("-" * 70)
            text_props_query = """
            CALL db.schema.nodeTypeProperties()
            YIELD nodeLabels, propertyName, propertyTypes
            WHERE 'String' IN propertyTypes
            RETURN nodeLabels, propertyName
            ORDER BY nodeLabels, propertyName
            """
            try:
                result = await session.run(text_props_query)
                text_props = {}
                async for record in result:
                    label = record["nodeLabels"][0] if record["nodeLabels"] else "Unknown"
                    prop = record["propertyName"]
                    if label not in text_props:
                        text_props[label] = []
                    text_props[label].append(prop)

                for label, props in sorted(text_props.items()):
                    print(f"  :{label}")
                    print(f"    String props: {', '.join(props[:6])}")
            except Exception as e:
                print(f"  Could not query schema: {e}")
                # Fallback: sample text from nodes
                print("  Sampling text properties from nodes...")
                for label in labels[:5]:
                    sample_q = f"MATCH (n:`{label}`) RETURN keys(n) AS keys LIMIT 1"
                    res = await session.run(sample_q)
                    rec = await res.single()
                    if rec:
                        print(f"  :{label} - {rec['keys']}")

            # 6. Check existing indexes
            print("\n## 6. EXISTING INDEXES")
            print("-" * 70)
            index_query = """
            SHOW INDEXES
            YIELD name, type, labelsOrTypes, properties, state
            RETURN name, type, labelsOrTypes, properties, state
            ORDER BY type, name
            """
            result = await session.run(index_query)
            has_vector = False
            has_fulltext = False
            async for record in result:
                idx_type = record["type"]
                if idx_type == "VECTOR":
                    has_vector = True
                if idx_type == "FULLTEXT":
                    has_fulltext = True
                print(f"  {record['name']} ({idx_type})")
                print(f"    Labels: {record['labelsOrTypes']}, Props: {record['properties']}")

            # 7. Find entities with most connections (good for demos)
            print("\n## 7. MOST CONNECTED ENTITIES (Good for Demo Queries)")
            print("-" * 70)
            connected_query = """
            MATCH (n)-[r]-()
            WITH n, labels(n)[0] AS label, count(r) AS rel_count
            ORDER BY rel_count DESC
            LIMIT 10
            RETURN
                coalesce(n.name, n.id, n.code, n.title, elementId(n)) AS identifier,
                label,
                rel_count
            """
            result = await session.run(connected_query)
            async for record in result:
                print(f"  {record['identifier']} ({record['label']}) - {record['rel_count']} connections")

            # 8. Suggest indexes
            print("\n## 8. SUGGESTED INDEXES")
            print("-" * 70)

            if not has_vector:
                print("\n  VECTOR INDEX: Not found")
                print("  Recommendation: Add vector index if you have text embeddings")
                print("  Example:")
                print("    CREATE VECTOR INDEX aircraft_embeddings FOR (n:SomeLabel)")
                print("    ON (n.embedding) OPTIONS {indexConfig: {")
                print("      `vector.dimensions`: 1536,")
                print("      `vector.similarity_function`: 'cosine'")
                print("    }}")

            if not has_fulltext:
                print("\n  FULLTEXT INDEX: Not found")
                print("  Recommendation: Add fulltext index for text search")
                # Find good candidates
                for label in labels[:5]:
                    props_q = f"MATCH (n:`{label}`) RETURN keys(n) AS keys LIMIT 1"
                    res = await session.run(props_q)
                    rec = await res.single()
                    if rec and rec["keys"]:
                        text_candidates = [k for k in rec["keys"] if k in ("name", "description", "title", "text", "content", "summary")]
                        if text_candidates:
                            print(f"  Example for {label}:")
                            print(f"    CREATE FULLTEXT INDEX {label.lower()}_search")
                            print(f"    FOR (n:{label}) ON EACH [n.{', n.'.join(text_candidates)}]")

            # 9. Propose retrieval query patterns
            print("\n## 9. PROPOSED RETRIEVAL QUERY PATTERNS")
            print("-" * 70)

            # Analyze graph structure for retrieval patterns
            print("\n  Based on the schema, here are potential retrieval patterns:\n")

            # Get a sample path to understand structure
            path_query = """
            MATCH path = (a)-[*1..2]-(b)
            WHERE a <> b
            RETURN
                [n IN nodes(path) | labels(n)[0]] AS node_labels,
                [r IN relationships(path) | type(r)] AS rel_types
            LIMIT 5
            """
            result = await session.run(path_query)
            paths = [record async for record in result]
            if paths:
                print("  Sample traversal patterns found:")
                for p in paths:
                    print(f"    {' -> '.join(p['node_labels'])} via {p['rel_types']}")

        print("\n" + "=" * 70)
        print("Exploration complete!")

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await driver.close()


def main() -> None:
    """Entry point."""
    asyncio.run(explore_aircraft_database())


if __name__ == "__main__":
    main()

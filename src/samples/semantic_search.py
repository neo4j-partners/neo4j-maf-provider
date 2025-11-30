"""
Demo: Semantic search over Neo4j graph database.

This sample demonstrates semantic search with graph-aware context retrieval
using Azure AI embeddings and Neo4j vector indexes.
"""

from __future__ import annotations

import asyncio


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


async def demo_semantic_search() -> None:
    """Demo: Semantic search over Neo4j graph database."""
    from logging_config import get_logger
    from neo4j_client import Neo4jClient, Neo4jSettings
    from vector_search import VectorSearchClient, VectorSearchConfig

    logger = get_logger()

    print_header("Demo: Semantic Search")
    print("This demo shows semantic search with graph-aware context retrieval.\n")

    neo4j_config = Neo4jSettings()
    vector_config = VectorSearchConfig()

    if not neo4j_config.is_configured:
        print("Error: Neo4j not configured.")
        print("Required environment variables:")
        print("  - NEO4J_URI")
        print("  - NEO4J_USERNAME")
        print("  - NEO4J_PASSWORD")
        return

    if not vector_config.is_configured:
        print("Error: Vector search not configured.")
        print("Required environment variables:")
        print("  - AZURE_AI_PROJECT_ENDPOINT")
        return

    print(f"Neo4j URI: {neo4j_config.uri}")
    print(f"Vector Index: {vector_config.vector_index_name}")
    print(f"Embedding Model: {vector_config.embedding_deployment}\n")

    neo4j_client = None
    try:
        neo4j_client = Neo4jClient(neo4j_config)
        await neo4j_client.connect()
        print("Connected to Neo4j!\n")

        # Get schema
        schema = await neo4j_client.get_schema()
        print(f"Graph Schema: {schema.summary()}")
        print(f"  Node labels: {', '.join(schema.node_labels[:5])}...")
        print(f"  Relationships: {', '.join(schema.relationship_types[:5])}...\n")

        # Create vector search client
        vector_client = VectorSearchClient(vector_config, neo4j_client)
        print("Vector search client initialized!\n")
        print("-" * 50)

        # Demo queries
        queries = [
            "What products does Microsoft offer?",
            "What are the risk factors for technology companies?",
            "Tell me about financial metrics and revenue",
        ]

        for i, query in enumerate(queries, 1):
            print(f"\n[Query {i}] {query}\n")
            results = await vector_client.search(query, top_k=3)

            if not results:
                print("  No results found.\n")
                continue

            for j, result in enumerate(results, 1):
                print(f"  Result {j} (score: {result.score:.3f}):")
                print(f"    Company: {result.metadata.company or 'N/A'}")
                text_preview = result.text[:150].replace("\n", " ")
                print(f"    Text: {text_preview}...")
                if result.metadata.risks:
                    print(f"    Related Risks: {', '.join(result.metadata.risks[:3])}")
                print()

            print("-" * 50)

        print(
            "\nDemo complete! Semantic search successfully retrieved graph-enriched results."
        )

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("Please check your Neo4j configuration and ensure the database is running.")
    except Exception as e:
        logger.error(f"Error during demo: {e}")
        print(f"\nError: {e}")
        raise
    finally:
        if neo4j_client:
            await neo4j_client.close()
            # Allow pending async cleanup tasks to complete
            await asyncio.sleep(0.1)

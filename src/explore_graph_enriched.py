"""
Explore Neo4j database for graph-enriched retrieval query patterns.

This script helps discover good retrieval_query patterns for the
Neo4jContextProvider's graph_enriched mode.

Run with: uv run python src/explore_graph_enriched.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from neo4j_client import Neo4jClient, Neo4jSettings
from util import get_env_file_path


async def explore_graph_patterns() -> None:
    """Explore graph patterns for retrieval queries."""
    env_path = get_env_file_path()
    if env_path:
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}\n")

    config = Neo4jSettings()
    if not config.is_configured:
        print("ERROR: Neo4j not configured.")
        return

    print(f"Connecting to Neo4j at: {config.uri}")
    print("=" * 70)

    async with Neo4jClient(config) as client:
        # 1. Check if chunks are linked to companies via documents
        print("\n## 1. Chunk -> Document -> Company Pattern")
        print("-" * 70)

        chunk_company_query = """
        MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(doc:Document)<-[:FILED]-(company:Company)
        RETURN company.name AS company, count(chunk) AS chunk_count
        ORDER BY chunk_count DESC
        LIMIT 5
        """
        results = await client.execute_query(chunk_company_query)
        for r in results:
            print(f"  {r['company']}: {r['chunk_count']} chunks")

        # 2. Check company -> risk factor relationships
        print("\n## 2. Company -> RiskFactor Pattern")
        print("-" * 70)

        risk_query = """
        MATCH (company:Company)-[:FACES_RISK]->(risk:RiskFactor)
        RETURN company.name AS company, collect(risk.name)[0..3] AS top_risks
        LIMIT 5
        """
        results = await client.execute_query(risk_query)
        for r in results:
            risks = ", ".join(r['top_risks']) if r['top_risks'] else "None"
            print(f"  {r['company']}: {risks}")

        # 3. Check company -> products
        print("\n## 3. Company -> Product Pattern")
        print("-" * 70)

        product_query = """
        MATCH (company:Company)-[:MENTIONS]->(product:Product)
        RETURN company.name AS company, collect(product.name)[0..3] AS top_products
        LIMIT 5
        """
        results = await client.execute_query(product_query)
        for r in results:
            products = ", ".join(r['top_products']) if r['top_products'] else "None"
            print(f"  {r['company']}: {products}")

        # 4. Sample the retrieval query pattern
        print("\n## 4. Sample Graph-Enriched Retrieval Pattern")
        print("-" * 70)

        enriched_query = """
        MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(doc:Document)<-[:FILED]-(company:Company)
        OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
        OPTIONAL MATCH (company)-[:MENTIONS]->(product:Product)
        WITH chunk, company,
             collect(DISTINCT risk.name)[0..3] AS risks,
             collect(DISTINCT product.name)[0..3] AS products
        RETURN
            chunk.text AS text,
            company.name AS company,
            company.ticker AS ticker,
            risks,
            products
        LIMIT 3
        """
        results = await client.execute_query(enriched_query)
        for i, r in enumerate(results, 1):
            print(f"\n  Result {i}:")
            print(f"    Company: {r['company']} ({r['ticker']})")
            print(f"    Risks: {', '.join(r['risks']) if r['risks'] else 'None'}")
            print(f"    Products: {', '.join(r['products']) if r['products'] else 'None'}")
            text = r['text'][:150] + "..." if len(r['text']) > 150 else r['text']
            print(f"    Text: {text}")

        # 5. Verify vector index exists
        print("\n## 5. Vector Index Check")
        print("-" * 70)

        index_query = """
        SHOW INDEXES
        YIELD name, type, labelsOrTypes, properties
        WHERE type = 'VECTOR'
        RETURN name, labelsOrTypes, properties
        """
        results = await client.execute_query(index_query)
        for r in results:
            print(f"  Index: {r['name']}")
            print(f"    Labels: {r['labelsOrTypes']}")
            print(f"    Properties: {r['properties']}")

        # 6. Recommend retrieval query
        print("\n## 6. RECOMMENDED RETRIEVAL QUERY FOR GRAPH-ENRICHED MODE")
        print("-" * 70)
        print("""
MATCH (node)-[:FROM_DOCUMENT]->(doc:Document)<-[:FILED]-(company:Company)
OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
OPTIONAL MATCH (company)-[:MENTIONS]->(product:Product)
WITH node, score, company, doc,
     collect(DISTINCT risk.name)[0..5] AS risks,
     collect(DISTINCT product.name)[0..5] AS products
RETURN
    node.text AS text,
    score,
    company.name AS company,
    company.ticker AS ticker,
    risks,
    products
ORDER BY score DESC
        """)

        print("\n" + "=" * 70)
        print("Exploration complete!")


def main() -> None:
    """Entry point."""
    asyncio.run(explore_graph_patterns())


if __name__ == "__main__":
    main()

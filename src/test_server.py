"""Simple script to test the API server."""

import argparse
import asyncio
import os

import httpx

BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


async def check_agent_status():
    """Check the agent status (GET /agent)."""
    print("Checking agent status...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/agent")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}\n")
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {BASE_URL}")
        print("Make sure the server is running:")
        print("  uv run uvicorn api.main:create_app --factory --reload\n")
        raise SystemExit(1)


async def chat_with_agent(message: str, conversation_id: str | None = None) -> str | None:
    """Send a message to the agent (POST /chat). Returns conversation_id for follow-ups."""
    print(f"Sending message: {message}")
    if conversation_id:
        print(f"  (continuing conversation: {conversation_id[:8]}...)")
    async with httpx.AsyncClient() as client:
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await client.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=60.0,
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data.get('response', data)}\n")
        return data.get("conversation_id")


async def chat_stream_with_agent(message: str, conversation_id: str | None = None) -> str | None:
    """Send a message using the streaming endpoint (POST /chat/stream)."""
    print(f"Sending message (stream): {message}")
    if conversation_id:
        print(f"  (continuing conversation: {conversation_id[:8]}...)")
    async with httpx.AsyncClient() as client:
        payload = {"message": message}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        response = await client.post(
            f"{BASE_URL}/chat/stream",
            json=payload,
            timeout=60.0,
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {data.get('response', data)}\n")
        return data.get("conversation_id")


async def get_graph_schema() -> dict | None:
    """Get the graph schema (GET /search/schema)."""
    print("Fetching graph schema...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/search/schema")
        print(f"Status: {response.status_code}")
        if response.status_code == 503:
            print("Graph schema not available (Neo4j not configured)\n")
            return None
        data = response.json()
        print(f"Node labels: {data.get('node_labels', [])}")
        print(f"Relationship types: {data.get('relationship_types', [])}\n")
        return data


async def semantic_search(query: str, top_k: int = 5) -> list | None:
    """Perform semantic search (POST /search/semantic)."""
    print(f"Semantic search: {query}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/search/semantic",
            json={"query": query, "top_k": top_k},
            timeout=60.0,
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 503:
            print("Semantic search not available (check Neo4j and Azure OpenAI config)\n")
            return None
        data = response.json()
        results = data.get("results", [])
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            text = result.get("text", "")[:100]
            metadata = result.get("metadata", {})
            company = metadata.get("company", "N/A")
            risks = metadata.get("risks", [])
            print(f"  {i}. [score={score:.3f}] Company: {company}")
            print(f"     Text: {text}...")
            if risks:
                print(f"     Risks: {', '.join(risks[:3])}")
        print()
        return results


async def get_entity_types() -> list | None:
    """Get available entity types (GET /search/entities/types)."""
    print("Fetching entity types...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/search/entities/types")
        print(f"Status: {response.status_code}")
        if response.status_code == 503:
            print("Entity search not available (Neo4j not configured)\n")
            return None
        data = response.json()
        entity_types = data.get("entity_types", [])
        print(f"Available entity types: {', '.join(entity_types)}\n")
        return entity_types


async def list_entities(entity_type: str, limit: int = 10) -> list | None:
    """List entities of a specific type (GET /search/entities/{entity_type})."""
    print(f"Listing {entity_type} entities (limit={limit})...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/search/entities/{entity_type}",
            params={"limit": limit},
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 503:
            print("Entity search not available (Neo4j not configured)\n")
            return None
        if response.status_code == 400:
            print(f"Invalid entity type: {response.json().get('detail', '')}\n")
            return None
        data = response.json()
        entities = data.get("entities", [])
        count = data.get("count", 0)
        print(f"Found {count} {entity_type} entities:")
        for i, entity in enumerate(entities, 1):
            print(f"  {i}. {entity.get('name', 'N/A')} (id: {entity.get('id', 'N/A')[:20]}...)")
        print()
        return entities


async def get_relationships(entity_name: str, limit: int = 10) -> list | None:
    """Get relationships for an entity (GET /search/entities/{entity_name}/relationships)."""
    print(f"Getting relationships for: {entity_name}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/search/entities/{entity_name}/relationships",
            params={"limit": limit},
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 503:
            print("Entity search not available (Neo4j not configured)\n")
            return None
        data = response.json()
        relationships = data.get("relationships", [])
        count = data.get("count", 0)
        print(f"Found {count} relationships:")
        for i, rel in enumerate(relationships, 1):
            source = rel.get("source", "?")
            source_type = rel.get("source_type", "?")
            relationship = rel.get("relationship", "?")
            target = rel.get("target", "?")
            target_type = rel.get("target_type", "?")
            print(f"  {i}. ({source_type}) {source}")
            print(f"      --[{relationship}]-->")
            print(f"      ({target_type}) {target}")
        print()
        return relationships


async def test_basic():
    """Basic test: check agent status and send a message."""
    print("=" * 50)
    print("Basic API Test")
    print(f"Target: {BASE_URL}")
    print("=" * 50 + "\n")

    await check_agent_status()
    await chat_with_agent("Hello, what can you do?")


async def test_memory():
    """Test conversation memory across multiple messages."""
    print("=" * 50)
    print("Conversation Memory Test")
    print(f"Target: {BASE_URL}")
    print("=" * 50 + "\n")

    await check_agent_status()

    print("--- Testing Conversation Memory ---\n")
    conversation_id = await chat_with_agent("Hello, what can you do?")
    await chat_with_agent("What was the last thing I asked you?", conversation_id)


async def test_stream():
    """Test the streaming endpoint."""
    print("=" * 50)
    print("Streaming Endpoint Test")
    print(f"Target: {BASE_URL}")
    print("=" * 50 + "\n")

    await check_agent_status()
    await chat_stream_with_agent(
        "Explain the history of artificial intelligence in 5 paragraphs"
    )


async def test_semantic():
    """Test semantic search over the graph database (optional - requires Neo4j + Azure OpenAI)."""
    print("=" * 50)
    print("Semantic Search Test (Optional)")
    print(f"Target: {BASE_URL}")
    print("=" * 50 + "\n")

    # First check if graph schema is available
    schema = await get_graph_schema()
    if schema is None:
        print("Skipping semantic search test - Neo4j not configured")
        return

    # Test semantic search with different queries
    print("--- Testing Semantic Search ---\n")

    await semantic_search("What products does Microsoft offer?", top_k=3)
    await semantic_search("What are the risk factors for Apple?", top_k=3)


async def test_entities():
    """Test entity search endpoints (optional - requires Neo4j)."""
    print("=" * 50)
    print("Entity Search Test (Optional)")
    print(f"Target: {BASE_URL}")
    print("=" * 50 + "\n")

    # First check available entity types
    entity_types = await get_entity_types()
    if entity_types is None:
        print("Skipping entity search test - Neo4j not configured")
        return

    print("--- Testing Entity Listing ---\n")

    # List companies
    companies = await list_entities("Company", limit=5)

    # List executives
    await list_entities("Executive", limit=5)

    # List risk factors
    await list_entities("RiskFactor", limit=5)

    print("--- Testing Relationship Queries ---\n")

    # Search for "Apple" which is known to have relationships in the test data
    await get_relationships("Apple", limit=5)


async def test_all():
    """Run all tests."""
    await test_basic()
    print("\n")
    await test_stream()
    print("\n")
    await test_memory()
    print("\n")
    await test_semantic()
    print("\n")
    await test_entities()


def main():
    parser = argparse.ArgumentParser(description="Test the AI Agent API server")
    parser.add_argument(
        "test",
        nargs="?",
        default="memory",
        choices=["basic", "memory", "stream", "semantic", "entities", "all"],
        help="Test to run: basic, memory, stream, semantic, entities, or all (default: memory)",
    )
    args = parser.parse_args()

    test_funcs = {
        "basic": test_basic,
        "memory": test_memory,
        "stream": test_stream,
        "semantic": test_semantic,
        "entities": test_entities,
        "all": test_all,
    }

    asyncio.run(test_funcs[args.test]())


if __name__ == "__main__":
    main()

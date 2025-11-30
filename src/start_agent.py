"""
Neo4j Context Provider Demo.

Demonstrates how the Neo4jContextProvider enhances agent responses
with knowledge graph data from Neo4j.

Run with: uv run start-agent
"""

import asyncio
import os
import sys

from agent_framework import ChatAgent
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

# Add src to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

from agent import AgentConfig, create_agent_client
from neo4j_client import Neo4jClient, Neo4jConfig
from neo4j_context_provider import Neo4jContextProvider
from util import get_env_file_path

# Demo queries that showcase the context provider
# Uses entity names that match the Neo4j database
DEMO_QUERIES = [
    "Tell me about APPLE INC and their products",
    "What do you know about MICROSOFT CORP?",
    "What relationships does AMAZON have?",
]


async def run_demo() -> None:
    """Run the context provider demo."""
    # Load environment
    env_path = get_env_file_path()
    if env_path:
        load_dotenv(env_path)

    print("=" * 70)
    print("NEO4J CONTEXT PROVIDER DEMO")
    print("=" * 70)
    print()
    print("This demo shows how the Neo4jContextProvider enhances agent responses")
    print("by injecting relevant knowledge graph data into the context.")
    print()

    # Initialize configurations
    agent_config = AgentConfig()
    neo4j_config = Neo4jConfig()

    if not neo4j_config.is_configured:
        print("ERROR: Neo4j not configured.")
        print("Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        return

    print(f"Agent: {agent_config.name} (model: {agent_config.model})")
    print(f"Neo4j: {neo4j_config.uri}")
    print()

    # Create clients
    credential = AzureCliCredential()
    chat_client = create_agent_client(agent_config, credential)
    neo4j_client = Neo4jClient(neo4j_config)

    # Create the context provider
    context_provider = Neo4jContextProvider(
        neo4j_client=neo4j_client,
        max_relationships=10,
    )

    print("-" * 70)
    print("STEP 1: Creating agent WITH Neo4j context provider")
    print("-" * 70)
    print()
    print("The context provider is configured with:")
    print("  - neo4j_client: Connected to Neo4j database")
    print("  - max_relationships: 10 (limit context size)")
    print()

    async with credential:
        async with chat_client:
            async with context_provider:
                print(f"[✓] Neo4j connected: {context_provider.is_connected}")
                print()

                # Create agent with the context provider
                async with ChatAgent(
                    chat_client=chat_client,
                    name=agent_config.name,
                    instructions=(
                        "You are a helpful assistant with access to a knowledge graph. "
                        "Use the knowledge graph context provided to give accurate, "
                        "specific answers about companies, executives, and products. "
                        "Reference specific relationships from the context in your answers."
                    ),
                    context_providers=context_provider,
                ) as agent:
                    print("-" * 70)
                    print("STEP 2: Running demo queries")
                    print("-" * 70)
                    print()
                    print("For each query, the context provider will:")
                    print("  1. Extract potential entity names from the query")
                    print("  2. Query Neo4j for relationships involving those entities")
                    print("  3. Format relationships as context instructions")
                    print("  4. Inject context into the agent's prompt")
                    print()

                    for i, query in enumerate(DEMO_QUERIES, 1):
                        print("=" * 70)
                        print(f"QUERY {i}: {query}")
                        print("=" * 70)
                        print()

                        # Show what the context provider does
                        print("[Context Provider Processing]")
                        print()

                        # Extract entities (same as provider does internally)
                        from agent_framework import ChatMessage
                        test_message = ChatMessage(role="user", text=query)

                        # Show extracted entities
                        entities = context_provider._extract_potential_entities(query)
                        print(f"  Extracted entities: {entities}")

                        # Query relationships for first entity
                        if entities and context_provider.is_connected:
                            try:
                                rels = await neo4j_client.get_entity_relationships(
                                    entity_name=entities[0],
                                    limit=5,
                                )
                                if rels:
                                    print(f"  Relationships found for '{entities[0]}':")
                                    for rel in rels[:3]:
                                        src = rel['source']
                                        r = rel['relationship']
                                        tgt = rel['target']
                                        print(f"    - {src} --[{r}]--> {tgt}")
                                    if len(rels) > 3:
                                        print(f"    ... and {len(rels) - 3} more")
                                else:
                                    print(f"  No relationships found for '{entities[0]}'")
                            except Exception as e:
                                print(f"  Error querying: {e}")
                        print()

                        # Run the agent with the query
                        print("[Agent Response]")
                        print()
                        try:
                            response = await agent.run(query)
                            # Print response, wrapping long lines
                            text = str(response)
                            for line in text.split('\n'):
                                print(f"  {line}")
                        except Exception as e:
                            print(f"  Error: {e}")

                        print()

    print("-" * 70)
    print("DEMO COMPLETE")
    print("-" * 70)
    print()
    print("The Neo4jContextProvider successfully enhanced the agent's responses")
    print("with knowledge graph data, enabling it to provide specific information")
    print("about entities and their relationships.")
    print()
    print("Key benefits demonstrated:")
    print("  - Automatic entity extraction from queries")
    print("  - Real-time relationship retrieval from Neo4j")
    print("  - Context injection without modifying the agent code")
    print("  - Seamless integration with Microsoft Agent Framework")
    print()


def main() -> None:
    """Entry point for the script."""
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\nDemo cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()

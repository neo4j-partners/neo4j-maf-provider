"""
Demo: Neo4j Memory Provider - Persistent Agent Memory.

This demo shows how the Neo4jContextProvider can store conversation memories
in Neo4j and retrieve them across different conversations. The provider
stores messages as Memory nodes and uses semantic search to find relevant
past conversations.

Key features demonstrated:
- Memory storage after each model invocation (invoked() method)
- Memory retrieval before each model invocation (invoking() method)
- User-scoped memory isolation (user A cannot see user B's memories)
- Cross-conversation memory persistence (new thread, same user)
"""

from __future__ import annotations

import asyncio

from samples.shared import print_header


async def demo_memory_basic() -> None:
    """Demo: Neo4j Memory Provider with persistent agent memory."""
    from azure.identity import DefaultAzureCredential
    from azure.identity.aio import AzureCliCredential

    from agent_framework_neo4j import (
        AzureAIEmbedder,
        AzureAISettings,
        Neo4jContextProvider,
        Neo4jSettings,
    )
    from samples.shared import AgentConfig, create_agent_client, get_logger

    logger = get_logger()

    print_header("Demo: Neo4j Memory Provider")
    print("This demo shows persistent agent memory using Neo4j.")
    print("Memories are stored after each interaction and retrieved")
    print("across different conversations for the same user.\n")

    # Load configs
    agent_config = AgentConfig()
    neo4j_settings = Neo4jSettings()
    azure_settings = AzureAISettings()

    if not agent_config.project_endpoint:
        print("Error: AZURE_AI_PROJECT_ENDPOINT not configured.")
        return

    if not neo4j_settings.is_configured:
        print("Error: Neo4j not configured.")
        print("Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        return

    if not azure_settings.is_configured:
        print("Error: Azure AI not configured.")
        print("Required: AZURE_AI_PROJECT_ENDPOINT")
        return

    print(f"Agent: {agent_config.name}")
    print(f"Model: {agent_config.model}")
    print(f"Neo4j URI: {neo4j_settings.uri}")
    print(f"Embedding Model: {azure_settings.embedding_model}\n")

    credential = AzureCliCredential()
    sync_credential = DefaultAzureCredential()
    embedder = None

    try:
        # Create embedder for semantic memory search
        embedder = AzureAIEmbedder(
            endpoint=azure_settings.inference_endpoint,
            credential=sync_credential,
            model=azure_settings.embedding_model,
        )
        print("Embedder initialized for memory search!\n")

        # First, demonstrate memory with User A
        # Note: memory_enabled=True and user_id provides scoping
        print("=" * 60)
        print("Part 1: User A - First Conversation")
        print("=" * 60 + "\n")

        provider_user_a = Neo4jContextProvider(
            uri=neo4j_settings.uri,
            username=neo4j_settings.username,
            password=neo4j_settings.get_password(),
            # Memory configuration
            memory_enabled=True,
            user_id="user_alice",  # Scope memories to this user
            # Use fulltext search for knowledge graph (no vector index needed)
            index_name=neo4j_settings.fulltext_index_name,
            index_type="fulltext",
            # Embedder is used for memory search
            embedder=embedder,
            top_k=3,
            context_prompt="## Knowledge Graph Context\nRelevant information:",
        )

        client = create_agent_client(agent_config, credential)

        async with provider_user_a:
            print("Connected to Neo4j with memory enabled!\n")
            print("Memory indexes will be created automatically on first use.\n")

            async with client.create_agent(
                name=agent_config.name,
                instructions=(
                    "You are a helpful personal assistant that remembers "
                    "information about users across conversations. When you "
                    "receive context about past conversations, use it to "
                    "provide personalized responses. Be friendly and concise."
                ),
                context_provider=provider_user_a,
            ) as agent:
                print("Agent created with memory provider!\n")
                print("-" * 50)

                # First conversation - share personal info
                print("\n[Turn 1] User A: Hi! I'm Alice and I love hiking.")
                response = await agent.run(
                    "Hi! I'm Alice and I love hiking in the mountains."
                )
                print(f"[Turn 1] Agent: {response.text}\n")

                print("-" * 50)
                print("\n[Turn 2] User A: My favorite trail is in Rocky Mountain NP")
                response = await agent.run(
                    "My favorite trail is Emerald Lake Trail in Rocky Mountain National Park."
                )
                print(f"[Turn 2] Agent: {response.text}\n")

        # Now start a NEW conversation for User A
        # The memory should persist from the previous conversation
        print("\n" + "=" * 60)
        print("Part 2: User A - New Conversation (Memory Test)")
        print("=" * 60 + "\n")

        # Create a fresh provider instance for new conversation
        provider_user_a_new = Neo4jContextProvider(
            uri=neo4j_settings.uri,
            username=neo4j_settings.username,
            password=neo4j_settings.get_password(),
            memory_enabled=True,
            user_id="user_alice",  # Same user - should see previous memories
            index_name=neo4j_settings.fulltext_index_name,
            index_type="fulltext",
            embedder=embedder,
            top_k=3,
        )

        async with provider_user_a_new:
            print("Started new conversation for User A...\n")

            async with client.create_agent(
                name=agent_config.name,
                instructions=(
                    "You are a helpful personal assistant that remembers "
                    "information about users across conversations. When you "
                    "receive context about past conversations, use it to "
                    "provide personalized responses. Be friendly and concise."
                ),
                context_provider=provider_user_a_new,
            ) as agent:
                print("-" * 50)

                # Test memory retrieval
                print("\n[Turn 1] User A: What outdoor activities do I enjoy?")
                response = await agent.run(
                    "What outdoor activities do I enjoy?"
                )
                print(f"[Turn 1] Agent: {response.text}\n")

                print("-" * 50)
                print("\n[Turn 2] User A: Where should I go this weekend?")
                response = await agent.run(
                    "Based on what you know about me, where should I go hiking this weekend?"
                )
                print(f"[Turn 2] Agent: {response.text}\n")

        # Demonstrate user isolation with User B
        print("\n" + "=" * 60)
        print("Part 3: User B - Memory Isolation")
        print("=" * 60 + "\n")

        provider_user_b = Neo4jContextProvider(
            uri=neo4j_settings.uri,
            username=neo4j_settings.username,
            password=neo4j_settings.get_password(),
            memory_enabled=True,
            user_id="user_bob",  # Different user - should NOT see Alice's memories
            index_name=neo4j_settings.fulltext_index_name,
            index_type="fulltext",
            embedder=embedder,
            top_k=3,
        )

        async with provider_user_b:
            print("Started conversation for User B (different user)...\n")

            async with client.create_agent(
                name=agent_config.name,
                instructions=(
                    "You are a helpful personal assistant that remembers "
                    "information about users across conversations. If you "
                    "don't have any context about the user, say so honestly."
                ),
                context_provider=provider_user_b,
            ) as agent:
                print("-" * 50)

                # User B should NOT see Alice's memories
                print("\n[Turn 1] User B: What outdoor activities do I enjoy?")
                response = await agent.run(
                    "What outdoor activities do I enjoy?"
                )
                print(f"[Turn 1] Agent: {response.text}\n")
                print("(Note: Agent should NOT know about Alice's hiking preferences)")

        print("-" * 50)
        print("\nDemo complete!")
        print("Key takeaways:")
        print("  - Memories persist across conversations for the same user")
        print("  - Memory scoping isolates data between users")
        print("  - Indexes are created automatically on first use")

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("Please check your Neo4j and Microsoft Foundry configuration.")
    except Exception as e:
        logger.error(f"Error during demo: {e}")
        print(f"\nError: {e}")
        raise
    finally:
        if embedder is not None:
            embedder.close()
        await credential.close()
        await asyncio.sleep(0.1)

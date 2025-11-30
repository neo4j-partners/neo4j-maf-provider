"""
Demo: Component Health Analysis with Graph-Enriched Context.

Shows fulltext search on components with graph traversal
to enrich results with aircraft, system, and maintenance context.

This demo uses the Aircraft database (AIRCRAFT_NEO4J_* env vars).
"""

from __future__ import annotations

import asyncio
import os


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


# Graph-enriched retrieval query for component health
# Traverses: Component <- System <- Aircraft, Component -> MaintenanceEvent
# Simplified to minimize context size
COMPONENT_RETRIEVAL_QUERY = """
MATCH (node)<-[:HAS_COMPONENT]-(sys:System)<-[:HAS_SYSTEM]-(aircraft:Aircraft)
OPTIONAL MATCH (node)-[:HAS_EVENT]->(event:MaintenanceEvent)
WITH node, score, aircraft, sys,
     count(event) AS event_count,
     collect(event.severity)[0] AS last_severity
RETURN
    node.name AS component,
    node.type AS type,
    aircraft.tail_number AS aircraft,
    sys.name AS system,
    event_count AS maintenance_events,
    last_severity AS severity
ORDER BY score DESC
"""


async def demo_component_health() -> None:
    """Demo: Component Health Analysis with graph-enriched context."""
    from azure.identity.aio import AzureCliCredential

    from agent import AgentConfig, create_agent_client
    from logging_config import get_logger
    from neo4j_provider import Neo4jContextProvider

    logger = get_logger()

    print_header("Demo: Component Health Analysis")
    print("This demo searches components using fulltext search")
    print("and enriches results with aircraft, system, and maintenance context.\n")

    # Load configs
    agent_config = AgentConfig()

    # Aircraft database credentials
    aircraft_uri = os.getenv("AIRCRAFT_NEO4J_URI")
    aircraft_username = os.getenv("AIRCRAFT_NEO4J_USERNAME")
    aircraft_password = os.getenv("AIRCRAFT_NEO4J_PASSWORD")

    if not agent_config.project_endpoint:
        print("Error: AZURE_AI_PROJECT_ENDPOINT not configured.")
        return

    if not all([aircraft_uri, aircraft_username, aircraft_password]):
        print("Error: Aircraft database not configured.")
        print("Required: AIRCRAFT_NEO4J_URI, AIRCRAFT_NEO4J_USERNAME, AIRCRAFT_NEO4J_PASSWORD")
        return

    print(f"Agent: {agent_config.name}")
    print(f"Model: {agent_config.model}")
    print(f"Aircraft DB: {aircraft_uri}")
    print(f"Index: component_search (fulltext)")
    print(f"Mode: graph_enriched\n")

    print("Graph Traversal Pattern:")
    print("-" * 50)
    print("  Component <- System <- Aircraft")
    print("  Component -> MaintenanceEvent (count)")
    print("  Returns: component, type, aircraft, system, events, severity")
    print("-" * 50 + "\n")

    credential = AzureCliCredential()

    try:
        # Create context provider with fulltext search
        # Use minimal top_k to avoid context overflow
        provider = Neo4jContextProvider(
            uri=aircraft_uri,
            username=aircraft_username,
            password=aircraft_password,
            index_name="component_search",
            index_type="fulltext",
            mode="graph_enriched",
            retrieval_query=COMPONENT_RETRIEVAL_QUERY,
            top_k=3,
            message_history_count=1,
            context_prompt=(
                "## Component Health Records\n"
                "Component data (name, type, aircraft, system, maintenance events):"
            ),
        )

        # Create agent client
        client = create_agent_client(agent_config, credential)

        async with provider:
            print("Connected to Aircraft database!\n")

            async with client.create_agent(
                name=agent_config.name,
                instructions=(
                    "You are an aircraft component analyst. Analyze component data and "
                    "explain maintenance history, system context, and health status. Be concise."
                ),
                context_providers=[provider],
            ) as agent:
                print("Agent created with component health context!\n")
                print("-" * 50)

                # Demo queries for component health analysis
                # Note: Queries should use terms in component name/type fields
                queries = [
                    "What turbine components have maintenance issues?",
                    "Tell me about fuel pump components and their maintenance",
                ]

                for i, query in enumerate(queries, 1):
                    print(f"\n[Query {i}] User: {query}\n")

                    response = await agent.run(query)
                    print(f"[Query {i}] Agent: {response.text}\n")
                    print("-" * 50)

                print(
                    "\nDemo complete! Fulltext search found components and "
                    "graph traversal enriched them with maintenance context."
                )

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("Please check your Aircraft Neo4j configuration.")
    except Exception as e:
        logger.error(f"Error during demo: {e}")
        print(f"\nError: {e}")
        raise
    finally:
        await credential.close()
        await asyncio.sleep(0.1)

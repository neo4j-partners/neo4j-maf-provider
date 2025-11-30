"""
Interactive demo for Neo4j MAF Provider capabilities.

Run with: uv run start-agent
Or directly: uv run start-agent 1  (for demo 1)
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from samples import (
    demo_agent_memory,
    demo_aircraft_flight_delays,
    demo_aircraft_maintenance_search,
    demo_component_health,
    demo_context_provider_basic,
    demo_context_provider_graph_enriched,
    demo_context_provider_vector,
    demo_semantic_search,
)
from util import get_env_file_path


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def print_menu() -> str | None:
    """Display menu and get user selection."""
    print_header("Neo4j MAF Provider Demo")
    print("Select a demo to run:\n")
    print("  -- Financial Documents Database --")
    print("  1. Agent Memory")
    print("  2. Semantic Search")
    print("  3. Context Provider (Fulltext)")
    print("  4. Context Provider (Vector)")
    print("  5. Context Provider (Graph-Enriched)")
    print("")
    print("  -- Aircraft Database --")
    print("  6. Aircraft Maintenance Search")
    print("  7. Flight Delay Analysis")
    print("  8. Component Health Analysis")
    print("")
    print("  A. Run all demos")
    print("  0. Exit\n")

    try:
        choice = input("Enter your choice (0-8, A): ").strip().upper()
        if choice in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "A"):
            return choice
        else:
            print("\nInvalid choice. Please enter 0-8 or A.")
            return None
    except (KeyboardInterrupt, EOFError):
        print("\n")
        return "0"


async def run_demo(choice: str) -> None:
    """Run the selected demo."""
    if choice == "1":
        await demo_agent_memory()
    elif choice == "2":
        await demo_semantic_search()
    elif choice == "3":
        await demo_context_provider_basic()
    elif choice == "4":
        await demo_context_provider_vector()
    elif choice == "5":
        await demo_context_provider_graph_enriched()
    elif choice == "6":
        await demo_aircraft_maintenance_search()
    elif choice == "7":
        await demo_aircraft_flight_delays()
    elif choice == "8":
        await demo_component_health()
    elif choice == "A":
        await demo_agent_memory()
        print("\n" + "=" * 60 + "\n")
        await demo_semantic_search()
        print("\n" + "=" * 60 + "\n")
        await demo_context_provider_basic()
        print("\n" + "=" * 60 + "\n")
        await demo_context_provider_vector()
        print("\n" + "=" * 60 + "\n")
        await demo_context_provider_graph_enriched()
        print("\n" + "=" * 60 + "\n")
        await demo_aircraft_maintenance_search()
        print("\n" + "=" * 60 + "\n")
        await demo_aircraft_flight_delays()
        print("\n" + "=" * 60 + "\n")
        await demo_component_health()


def main() -> None:
    """Main entry point for the demo CLI."""
    parser = argparse.ArgumentParser(
        description="Neo4j MAF Provider Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run start-agent        Interactive menu
  uv run start-agent 1      Run demo 1 (Agent Memory)
  uv run start-agent 2      Run demo 2 (Semantic Search)
  uv run start-agent 3      Run demo 3 (Context Provider - Fulltext)
  uv run start-agent 4      Run demo 4 (Context Provider - Vector)
  uv run start-agent 5      Run demo 5 (Context Provider - Graph-Enriched)
  uv run start-agent 6      Run demo 6 (Aircraft Maintenance Search)
  uv run start-agent 7      Run demo 7 (Flight Delay Analysis)
  uv run start-agent 8      Run demo 8 (Component Health Analysis)
  uv run start-agent a      Run all demos
""",
    )
    parser.add_argument(
        "demo",
        nargs="?",
        type=str,
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "a", "A"],
        help="Demo to run: 1-5=Financial, 6-8=Aircraft, a=All",
    )
    args = parser.parse_args()

    # Load environment
    env_file = get_env_file_path()
    if env_file:
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
    else:
        print("Using system environment variables")

    # If demo specified on command line, run it directly
    if args.demo:
        try:
            asyncio.run(run_demo(args.demo.upper()))
        except KeyboardInterrupt:
            print("\n\nDemo interrupted.")
        return

    # Interactive menu mode
    while True:
        choice = print_menu()

        if choice is None:
            continue
        elif choice == "0":
            print("\nGoodbye!")
            sys.exit(0)
        else:
            try:
                asyncio.run(run_demo(choice))
            except KeyboardInterrupt:
                print("\n\nDemo interrupted.")

            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

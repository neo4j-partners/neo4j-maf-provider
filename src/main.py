"""
Interactive demo for Neo4j MAF Provider capabilities.

Run with: uv run start-agent
Or directly: uv run start-agent 1  (for demo 1)
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from collections.abc import Awaitable, Callable

from samples import (
    demo_aircraft_flight_delays,
    demo_aircraft_maintenance_search,
    demo_azure_thread_memory,
    demo_component_health,
    demo_context_provider_basic,
    demo_context_provider_graph_enriched,
    demo_context_provider_vector,
    demo_semantic_search,
)
from samples._utils import print_header
from utils import get_env_file_path

# Demo function type
DemoFunc = Callable[[], Awaitable[None]]

# Map demo choices to their functions
DEMOS: dict[str, DemoFunc] = {
    "1": demo_azure_thread_memory,
    "2": demo_semantic_search,
    "3": demo_context_provider_basic,
    "4": demo_context_provider_vector,
    "5": demo_context_provider_graph_enriched,
    "6": demo_aircraft_maintenance_search,
    "7": demo_aircraft_flight_delays,
    "8": demo_component_health,
}


def print_menu() -> str | None:
    """Display menu and get user selection."""
    print_header("Neo4j MAF Provider Demo")
    print("Select a demo to run:\n")
    print("  -- Azure Agent Framework --")
    print("  1. Azure Thread Memory (no Neo4j)")
    print("")
    print("  -- Financial Documents Database --")
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
    if choice == "A":
        # Run all demos sequentially
        demo_list = list(DEMOS.values())
        for i, demo_func in enumerate(demo_list):
            await demo_func()
            if i < len(demo_list) - 1:
                print("\n" + "=" * 60 + "\n")
    elif choice in DEMOS:
        await DEMOS[choice]()


def main() -> None:
    """Main entry point for the demo CLI."""
    parser = argparse.ArgumentParser(
        description="Neo4j MAF Provider Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run start-agent        Interactive menu
  uv run start-agent 1      Run demo 1 (Azure Thread Memory)
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

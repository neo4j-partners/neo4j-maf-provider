# Neo4j Context Provider for Microsoft Agent Framework

A context provider that enables AI agents to retrieve knowledge graph context from Neo4j, supporting both vector and fulltext search with optional graph enrichment.

## What is a Context Provider?

Context providers are plugins for the [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) that automatically inject relevant information into an agent's conversation before the AI model processes each message. The Neo4j Context Provider retrieves data from your Neo4j knowledge graph—whether through semantic vector search or keyword-based fulltext search—and enriches agent responses with graph-aware context.

For detailed architecture, configuration options, and sample walkthroughs, see **[NEO4J_PROVIDER_ARCHITECTURE.md](NEO4J_PROVIDER_ARCHITECTURE.md)**.

## Prerequisites

- **[uv](https://github.com/astral-sh/uv)**: Fast Python package installer
- **[Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)**: For infrastructure provisioning
- **[Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)**: For authentication
- **Neo4j Database**: With vector or fulltext indexes configured

## Getting Started

### 1. Provision Azure Infrastructure

Deploy Microsoft Foundry resources (for embeddings and chat models):

```bash
azd up
```

### 2. Install Dependencies

```bash
uv sync --prerelease=allow
```

### 3. Setup Environment Variables

Pull environment variables from azd and create a local `.env` file:

```bash
uv run setup_env.py
```

Add your Neo4j credentials to `.env`:

```
NEO4J_URI=neo4j+s://your-database.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_INDEX_NAME=your-index-name
```

### 4. Run the Samples

Launch the interactive demo menu:

```bash
uv run start-agent
```

Or run a specific sample directly:

```bash
uv run start-agent 3    # Run Context Provider (Fulltext)
uv run start-agent a    # Run all samples
```

## Samples

The `src/samples/` directory contains working examples. Run them using `uv run start-agent`:

| # | Sample | Description |
|---|--------|-------------|
| 1 | `agent_memory.py` | Agent Framework conversation memory using threads |
| 2 | `semantic_search.py` | Direct vector search without Agent Framework |
| 3 | `context_provider_basic.py` | Fulltext (keyword) search |
| 4 | `context_provider_vector.py` | Vector search with Microsoft Foundry embeddings |
| 5 | `context_provider_graph_enriched.py` | Graph traversal for rich context |
| 6 | `aircraft_maintenance_search.py` | Aircraft domain with custom retrieval queries |
| 7 | `aircraft_flight_delays.py` | Flight operations data analysis |
| 8 | `component_health.py` | Component status with aggregated maintenance counts |

See [NEO4J_PROVIDER_ARCHITECTURE.md](NEO4J_PROVIDER_ARCHITECTURE.md) for detailed walkthroughs of each sample.

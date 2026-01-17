# Neo4j Context Provider Samples

Sample applications demonstrating the `agent-framework-neo4j` library with Microsoft Agent Framework.

## How It Works

These samples use **Azure AI Foundry serverless models** to power the AI agents. The infrastructure is minimal:

- **AI Project** - A Microsoft Foundry project for managing model endpoints
- **Serverless Models** - Pay-as-you-go model deployments (GPT-4o, text-embedding-ada-002)

When you run a sample, the agent:
1. Receives your question
2. The Neo4j Context Provider searches the knowledge graph for relevant information
3. Retrieved context is injected into the conversation
4. The model generates a response grounded in the knowledge graph data

## Prerequisites

- Azure subscription with access to Azure AI services
- Azure CLI and Azure Developer CLI (`azd`) installed
- Neo4j database with your data (samples use two demo databases)
- Python 3.10+ and `uv` package manager

## Quick Start

```bash
# 1. Install dependencies (from repo root)
uv sync --prerelease=allow

# 2. Configure Azure region (from samples directory)
cd samples
./scripts/setup_azure.sh

# 3. Deploy Azure infrastructure (includes model deployments)
azd up

# 4. Sync Azure environment variables
uv run setup_env.py

# 5. Add Neo4j credentials to .env

# 6. Run samples
uv run start-samples
```

## 1. Deploy Azure Infrastructure

First, configure your Azure region:

```bash
cd samples
./scripts/setup_azure.sh
```

Then deploy the infrastructure:

```bash
azd up
```

This provisions:
- Azure AI Services account
- Azure AI Project
- Model deployments (GPT-4o, text-embedding-ada-002)
- Required IAM role assignments

After provisioning, sync the Azure endpoints to your `.env` file:

```bash
uv run setup_env.py
```

This populates your `.env` with:
```
AZURE_AI_PROJECT_ENDPOINT=https://...
AZURE_AI_MODEL_NAME=gpt-4o
AZURE_AI_EMBEDDING_NAME=text-embedding-ada-002
```

## 2. Configure Neo4j

Add your Neo4j database credentials to `.env`:

### Financial Documents Database (samples 1-5)

See [SETUP.md](SETUP.md) for instructions on setting up the Neo4j database with financial data.

### Aircraft Database (samples 6-8)

For aircraft database access, please contact the author.

## 3. Run Samples

### Interactive Menu

```bash
uv run start-samples
```

### Run Specific Sample

```bash
uv run start-samples 1   # Azure Thread Memory
uv run start-samples 2   # Semantic Search
uv run start-samples 3   # Context Provider (Fulltext)
uv run start-samples 4   # Context Provider (Vector)
uv run start-samples 5   # Context Provider (Graph-Enriched)
uv run start-samples 6   # Aircraft Maintenance Search
uv run start-samples 7   # Flight Delay Analysis
uv run start-samples 8   # Component Health Analysis
uv run start-samples 9   # Neo4j Memory Provider
uv run start-samples a   # Run all demos
```

## Available Samples

### Basic Fulltext (`basic_fulltext/`)

- **main.py** - Basic fulltext search context provider
- **azure_thread_memory.py** - Azure Agent Framework thread memory demo

### Vector Search (`vector_search/`)

- **main.py** - Vector similarity search with embeddings
- **semantic_search.py** - Semantic search capabilities

### Graph Enriched (`graph_enriched/`)

- **main.py** - Graph traversal after initial search for rich context

### Aircraft Domain (`aircraft_domain/`)

Domain-specific samples using an aircraft maintenance database:

- **maintenance_search.py** - Search maintenance events with aircraft context
- **flight_delays.py** - Analyze flight delays with route information
- **component_health.py** - Component health analysis with system hierarchy

### Memory Provider (`memory_basic/`)

Demonstrates persistent agent memory using Neo4j as the storage backend:

- **main.py** - Complete memory demonstration showing:
  - Memory storage after each model invocation
  - Cross-conversation memory retrieval
  - User-scoped memory isolation
  - Semantic search for relevant memories

**Key Features:**
- Memories persist across conversation sessions
- Semantic vector search finds related memories even with different phrasing
- User isolation prevents cross-user data leakage
- Indexes created automatically on first use (lazy initialization)

**Example output:**
```
[Query] What's my dog's name?
  Expected: Should recall: Max, golden retriever
  Agent: Your dog's name is Max. He's a golden retriever who loves to play fetch!

[Query] Do I have any pets?
  Note: Semantically related to 'golden retriever named Max'
  Agent: Yes, you have a golden retriever named Max who loves to play fetch.
```

## Directory Structure

```
samples/
├── azure.yaml              # Azure Developer CLI configuration
├── setup_env.py            # Sync Azure env vars to .env
├── infra/                  # Azure Bicep templates
│   └── main.bicep          # AI Services, Project, and model deployments
├── scripts/                # Setup helper scripts
├── src/samples/
│   ├── basic_fulltext/     # Fulltext search samples
│   ├── vector_search/      # Vector similarity samples
│   ├── graph_enriched/     # Graph traversal samples
│   ├── aircraft_domain/    # Aircraft maintenance samples
│   ├── memory_basic/       # Neo4j memory provider sample
│   └── shared/             # Shared utilities (agent config, CLI, logging)
```

## Troubleshooting

### "Model deployment not found"

Run `azd up` to deploy the infrastructure including model deployments, then run `uv run setup_env.py` to sync the model names to your `.env` file.

### "Neo4j not configured"

Add the required Neo4j environment variables to `.env`. The samples check for:
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (financial database)
- `AIRCRAFT_NEO4J_URI`, `AIRCRAFT_NEO4J_USERNAME`, `AIRCRAFT_NEO4J_PASSWORD` (aircraft database)

### "Azure not configured"

Run `azd up` followed by `uv run setup_env.py` to populate Azure variables.

### "Index not found"

Create the required indexes in your Neo4j database. See `SETUP.md` for details.

## Cost Estimate

With serverless models, you only pay for what you use:

- **Chat model (GPT-4o)**: ~$0.01-0.03 per 1K tokens
- **Embedding model**: ~$0.0001 per 1K tokens
- **Running all 9 demos**: approximately $0.10-0.30 total

No idle costs - the AI Services account itself has no ongoing charges when not in use.

# Neo4j Context Provider Samples

Sample applications demonstrating the `agent-framework-neo4j` library with Microsoft Agent Framework.

## How It Works

These samples use **Microsoft Foundry** (Azure AI) to power the AI agents. The infrastructure provisions:

- **AI Project** - A Microsoft Foundry project that hosts your AI resources
- **GPT-4o Model** - Chat model deployment for agent conversations
- **text-embedding-ada-002** - Embedding model for vector search (converts text to vectors)
- **Monitoring** - Application Insights and Log Analytics for observability

When you run a sample, the agent:
1. Receives your question
2. The Neo4j Context Provider searches the knowledge graph for relevant information
3. Retrieved context is injected into the conversation
4. The GPT-4o model generates a response grounded in the knowledge graph data

## Prerequisites

- Azure subscription with access to Azure AI services
- Azure CLI and Azure Developer CLI (`azd`) installed
- Neo4j database with your data (samples use two demo databases)
- Python 3.10+ and `uv` package manager

## 1. Provision Infrastructure

The infrastructure uses Azure Bicep templates to deploy Microsoft Foundry resources.

```bash
# Install dependencies (from repo root)
uv sync --prerelease=allow

# Deploy Azure infrastructure (from samples directory)
cd samples
./scripts/setup_azure.sh   # Configure region (required before first deploy)
azd up
```

This provisions:
- Azure AI Project with model deployments
- Storage account for AI project data
- Application Insights for monitoring
- Required IAM role assignments

> **Note:** If provisioning fails with a `RequestConflict` error about "provisioning state is not terminal", simply run `azd up` again. This is a transient Azure timing issue—the retry will continue from where it left off.

After provisioning, sync the Azure endpoints to your `.env` file:

```bash
uv run setup_env.py
```

This pulls `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_NAME`, and `AZURE_AI_EMBEDDING_NAME` from the deployed infrastructure while preserving your Neo4j credentials.

## 2. Configure Neo4j

Add your Neo4j database credentials to `.env`:

### Financial Documents Database (samples 1-5)

```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_VECTOR_INDEX_NAME=chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME=search_chunks
```

### Aircraft Database (samples 6-8)

```
AIRCRAFT_NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
AIRCRAFT_NEO4J_USERNAME=neo4j
AIRCRAFT_NEO4J_PASSWORD=your-password
```

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

## Directory Structure

```
samples/
├── azure.yaml              # Azure Developer CLI configuration
├── setup_env.py            # Sync Azure env vars to .env
├── infra/                  # Azure Bicep templates
│   ├── main.bicep          # Main deployment orchestration
│   ├── api.bicep           # Optional Container App deployment
│   └── core/               # Modular templates (AI, security, monitoring)
├── scripts/                # Setup helper scripts
│   ├── setup_azure.sh      # Interactive Azure region configuration
│   └── setup_aircraft_indexes.py  # Create Neo4j indexes for aircraft samples
├── basic_fulltext/         # Fulltext search samples
├── vector_search/          # Vector similarity samples
├── graph_enriched/         # Graph traversal samples
├── aircraft_domain/        # Aircraft maintenance samples
└── shared/                 # Shared utilities (agent config, CLI, logging)
```

# Neo4j Context Provider for Microsoft Agent Framework

A context provider that enables AI agents to retrieve knowledge from Neo4j graph databases.

## What is a Context Provider?

Context providers are an extensibility mechanism in the Microsoft Agent Framework that automatically inject relevant information into an agent's conversation before the AI model processes each message. They solve a fundamental problem: how do you give an AI agent access to your organization's knowledge without manually copy-pasting information into every conversation?

```
User sends message
       ↓
Agent Framework calls context provider's "invoking" method
       ↓
Provider searches external data source for relevant information
       ↓
Provider returns context to the agent
       ↓
Agent sends message + context to the AI model
       ↓
AI model responds with knowledge from your data
```

Context providers work behind the scenes to:
1. **Retrieve relevant information** from external sources (databases, search indexes, APIs)
2. **Inject that information** into the agent's context before it responds
3. **Update state or memory** after the agent responds

---

**This README covers running the samples.** For other topics:
- **Building and publishing** the library to PyPI: [docs/PUBLISH.md](docs/PUBLISH.md)
- **Detailed architecture** and design principles: [docs/architecture.md](docs/architecture.md)

---

## The Neo4j Context Provider

This provider connects AI agents to Neo4j knowledge graphs. It supports:

| Search Type | Description |
|-------------|-------------|
| **Vector** | Semantic similarity search using embeddings |
| **Fulltext** | Keyword matching using BM25 scoring |
| **Hybrid** | Combined vector + fulltext for best results |

| Mode | Description |
|------|-------------|
| **Basic** | Returns search results directly |
| **Graph-Enriched** | Traverses relationships after search for rich context |

**Key design principles:**
- **No entity extraction** - Full message text is passed to the search index; Neo4j handles relevance ranking
- **Index-driven configuration** - Works with any Neo4j index; configure `index_name` and `index_type`
- **Configurable graph enrichment** - Custom Cypher queries traverse relationships after initial search

## Installation

```bash
pip install agent-framework-neo4j --pre

# With Azure AI embeddings support
pip install agent-framework-neo4j[azure] --pre
```

## Setting up Neo4j

You have several options to set up Neo4j:

### Option A: Neo4j AuraDB (Recommended)

Get a free cloud instance at https://neo4j.com/cloud/aura-free/

### Option B: Local Neo4j with Docker

```bash
docker run --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -d neo4j:5
```

### Option C: Neo4j Desktop

Download from https://neo4j.com/download/

## Getting Started with the Neo4j MAF Provider

Follow these steps to run the sample applications and see the context provider in action.

### Step 1: Install Dependencies

```bash
# Clone the repository
git clone https://github.com/yourorg/neo4j-maf-provider.git
cd neo4j-maf-provider

# Install all workspace packages
uv sync --prerelease=allow
```

### Step 2: Provision Azure Infrastructure

The samples use Azure AI Foundry serverless models. You need to provision a Foundry project and deploy models.

```bash
cd samples

# Configure your Azure region
./scripts/setup_azure.sh

# Deploy Azure infrastructure (creates AI Project + model deployments)
azd up

# Sync Azure environment variables to .env
uv run setup_env.py
```

This provisions:
- **Azure AI Project** - A Microsoft Foundry project for managing model endpoints
- **Serverless Models** - GPT-4o for chat, text-embedding-ada-002 for embeddings

### Step 3: Configure Neo4j

Add your Neo4j database credentials to `samples/.env`:

```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
```

### Step 4: Run the Samples

```bash
uv run start-samples      # Interactive menu
uv run start-samples 3    # Run specific demo
```

See [samples/README.md](samples/README.md) for complete setup instructions including prerequisites, database configuration, and troubleshooting.

## Available Samples

| Sample | Search Type | Context Provider Usage |
|--------|-------------|------------------------|
| **Basic Fulltext** | Fulltext (BM25) | Uses `index_type="fulltext"` to search Neo4j fulltext indexes with keyword matching |
| **Vector Search** | Vector | Uses `index_type="vector"` with an embedder to perform semantic similarity search |
| **Graph-Enriched** | Vector + Cypher | Uses `index_type="vector"` with `retrieval_query` to traverse graph relationships after initial vector search |
| **Aircraft Maintenance** | Fulltext + Cypher | Uses `index_type="fulltext"` with `retrieval_query` to enrich maintenance events with aircraft/system/component context |
| **Flight Delays** | Fulltext + Cypher | Uses `index_type="fulltext"` with `retrieval_query` to enrich delay records with flight/aircraft/route context |
| **Component Health** | Fulltext + Cypher | Uses `index_type="fulltext"` with `retrieval_query` to traverse component → system → aircraft hierarchy |

## Development

### Run Tests

```bash
uv run pytest
```

### Build the Library

```bash
uv build --package agent-framework-neo4j
```

### Type Checking and Linting

```bash
uv run mypy packages/agent-framework-neo4j/agent_framework_neo4j
uv run ruff check packages/agent-framework-neo4j/agent_framework_neo4j
```

## Publishing to PyPI

```bash
# Bump version
./scripts/version-bump.sh patch   # or major/minor

# Build and publish
uv build --package agent-framework-neo4j
uv publish --token $PYPI_TOKEN
```

See [docs/PUBLISH.md](docs/PUBLISH.md) for the complete publishing guide including authentication options and TestPyPI testing.

## Project Structure

```
neo4j-maf-provider/
├── packages/agent-framework-neo4j/   # Publishable PyPI library
├── samples/                           # Self-contained demo applications
│   ├── azure.yaml                     # Azure Developer CLI config
│   ├── infra/                         # Azure Bicep templates
│   └── ...
├── tests/                             # Library tests
└── docs/                              # Documentation
```

## Packages

### agent-framework-neo4j

The core library providing Neo4j context for Microsoft Agent Framework agents.

```bash
pip install agent-framework-neo4j --pre
```

**Public API:**
- `Neo4jContextProvider` - Main context provider class
- `Neo4jSettings` - Pydantic settings for Neo4j connection
- `AzureAISettings` - Pydantic settings for Azure AI
- `AzureAIEmbedder` - Azure AI embedding integration
- `FulltextRetriever` - Fulltext search retriever

**Basic usage:**
```python
from agent_framework_neo4j import Neo4jContextProvider, Neo4jSettings

settings = Neo4jSettings()  # Loads from environment

provider = Neo4jContextProvider(
    uri=settings.uri,
    username=settings.username,
    password=settings.get_password(),
    index_name="chunkEmbeddings",
    index_type="vector",
    embedder=my_embedder,
)

async with provider:
    # Use with Microsoft Agent Framework
    pass
```

See [packages/agent-framework-neo4j/README.md](packages/agent-framework-neo4j/README.md) for detailed API documentation.

### neo4j-provider-samples

Demo applications in `samples/` showing the library in action:
- Basic fulltext search
- Vector similarity search
- Graph-enriched context
- Aircraft domain examples

See [samples/README.md](samples/README.md) for setup and usage.

## Documentation

**Project docs:**
- [Architecture](docs/architecture.md) - Design principles, search flow, components
- [Publishing Guide](docs/PUBLISH.md) - Build and publish to PyPI

**External resources:**
- [Microsoft Agent Framework](https://aka.ms/agent-framework)
- [Agent Framework Python Packages](https://github.com/microsoft/agent-framework/tree/main/python/packages)
- [Neo4j GraphRAG Python](https://neo4j.com/docs/neo4j-graphrag-python/)
- [Neo4j AuraDB](https://neo4j.com/cloud/aura/)

## License

MIT

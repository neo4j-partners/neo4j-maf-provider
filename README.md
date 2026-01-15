# neo4j-maf-provider

Monorepo containing the Neo4j Context Provider for Microsoft Agent Framework.

## Structure

```
neo4j-maf-provider/
├── packages/agent-framework-neo4j/   # Publishable PyPI library
├── samples/                           # Demo applications (self-contained)
│   ├── azure.yaml                     #   azd configuration
│   ├── infra/                         #   Azure Bicep templates
│   ├── scripts/                       #   Setup scripts
│   └── ...                            #   Sample applications
├── tests/                             # Library tests
└── docs/                              # Documentation
```

## Quick Start

### Setup

```bash
# Install all workspace packages
uv sync --prerelease=allow

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Run Samples

```bash
# Interactive menu
uv run start-samples

# Run specific sample
uv run start-samples 3
```

### Run Tests

```bash
uv run pytest
```

## Packages

### agent-framework-neo4j

The core library providing Neo4j context for Microsoft Agent Framework agents.

```bash
pip install agent-framework-neo4j --pre
```

**Features:**
- Vector, fulltext, and hybrid search modes
- Graph-enriched retrieval with custom Cypher queries
- Configurable message history windowing
- Compatible with neo4j-graphrag retrievers

See [packages/agent-framework-neo4j/README.md](packages/agent-framework-neo4j/README.md) for details.

### neo4j-provider-samples

Demo applications showcasing the library:

- Basic fulltext search
- Vector similarity search
- Graph-enriched context
- Aircraft domain examples

See [samples/README.md](samples/README.md) for details.

## Development

```bash
# Install with dev dependencies
uv sync --prerelease=allow

# Run tests
uv run pytest

# Type checking
uv run mypy packages/agent-framework-neo4j/src/agent_framework_neo4j

# Linting
uv run ruff check packages/agent-framework-neo4j/src
uv run ruff format packages/agent-framework-neo4j/src
```

## Publishing

```bash
# Build the library package
uv build --package agent-framework-neo4j

# Publish to PyPI
uv publish --package agent-framework-neo4j
```

## Environment Variables

### Neo4j Connection

```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_VECTOR_INDEX_NAME=chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME=search_chunks
```

### Azure AI (for embeddings and chat)

```
AZURE_AI_PROJECT_ENDPOINT=https://your-project.cognitiveservices.azure.com
AZURE_AI_MODEL_NAME=gpt-4o
AZURE_AI_EMBEDDING_NAME=text-embedding-ada-002
```

## Documentation

- [Library README](packages/agent-framework-neo4j/README.md)
- [Samples README](samples/README.md)
- [Architecture Guide](NEO4J_PROVIDER_ARCHITECTURE.md)
- [Microsoft Agent Framework](https://aka.ms/agent-framework)

## License

MIT

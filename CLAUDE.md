# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Guidelines

- When proposing new features, write proposals in plain English only (no code). Keep proposals simple—this is a demo project.
- Use Python best practices and pydantic type safety where possible.
- **Always use the latest version of the Microsoft Agent Framework with Microsoft Foundry** for agent-related functionality. Reference the framework source at `/Users/ryanknight/projects/azure/agent-framework` and samples at `/Users/ryanknight/projects/azure/Agent-Framework-Samples`. See `AGENT_FRAMEWORK.md` for details.

## Project Overview

This is a **Neo4j Context Provider** for the Microsoft Agent Framework. Context providers are plugins that automatically inject relevant information into an agent's conversation before the AI model processes each message. This provider retrieves data from Neo4j knowledge graphs using vector or fulltext search, with optional graph traversal for rich context.

Key architecture:
- **No entity extraction**: Full message text is passed to the search index, letting Neo4j handle relevance ranking
- **Index-driven configuration**: Works with any Neo4j index—configure `index_name` and `index_type`
- **Configurable graph enrichment**: Custom Cypher queries traverse relationships after initial search

## Commands

### Setup
```bash
azd up                         # Provision Azure infrastructure (Microsoft Foundry)
uv sync --prerelease=allow     # Install dependencies (pre-release required for Agent Framework)
uv run setup_env.py            # Pull env vars from azd into .env
```

### Run Demos
```bash
uv run start-agent             # Interactive menu
uv run start-agent 3           # Run specific demo (1-8)
uv run start-agent a           # Run all demos
```

### Run API Server
```bash
uv run uvicorn api.main:create_app --factory --reload
```

## Architecture

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `Neo4jContextProvider` | `src/neo4j_provider/provider.py` | Main context provider implementing `ContextProvider` interface |
| `VectorizerProtocol` | `src/neo4j_provider/provider.py` | Protocol for embedding text (compatible with redisvl) |
| `Neo4jClient` | `src/neo4j_client.py` | Async Neo4j driver wrapper with connection management |
| `Neo4jSettings` | `src/neo4j_client.py` | Pydantic settings for Neo4j credentials |

### Search Flow

1. **invoking()** called → Provider receives conversation messages
2. Filter to USER/ASSISTANT messages, take recent N messages
3. Concatenate message text (no entity extraction)
4. Execute search based on `index_type`:
   - **vector**: Embed query → `db.index.vector.queryNodes()`
   - **fulltext**: Optional stop word filtering → `db.index.fulltext.queryNodes()`
5. If `mode="graph_enriched"`: Execute custom `retrieval_query` Cypher
6. Format results → Return `Context(messages=[...])`

### Samples (src/samples/)

Two databases are used in demos:
- **Financial Documents** (samples 1-5): SEC filings with Company, Document, Chunk, RiskFactor, Product nodes
- **Aircraft Domain** (samples 6-8): Maintenance events, components, flights, delays

## Environment Variables

### Neo4j Connection
```
NEO4J_URI                     # neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME
NEO4J_PASSWORD
NEO4J_VECTOR_INDEX_NAME       # default: chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME     # default: search_chunks
```

### Azure/Microsoft Foundry (populated by setup_env.py)
```
AZURE_AI_PROJECT_ENDPOINT     # Microsoft Foundry project endpoint
AZURE_AI_MODEL_NAME           # Chat model (default: gpt-4o)
AZURE_AI_EMBEDDING_NAME       # Embedding model (default: text-embedding-ada-002)
```

## Key Patterns

### Creating a Context Provider
```python
provider = Neo4jContextProvider(
    index_name="chunkEmbeddings",
    index_type="vector",  # or "fulltext"
    mode="graph_enriched",  # or "basic"
    retrieval_query="""
        MATCH (node)-[:FROM_DOCUMENT]->(doc)
        RETURN node.text AS text, score, doc.title AS title
        ORDER BY score DESC
    """,
    vectorizer=my_vectorizer,
    top_k=5,
)

async with provider:
    # Use with agent
```

### Retrieval Query Requirements
- Must use `node` and `score` variables from index search
- Must return at least `text` and `score` columns
- Use `ORDER BY score DESC` to maintain relevance ranking

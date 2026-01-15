# Architecture

## Overview

The Neo4j Context Provider integrates Neo4j knowledge graphs with Microsoft Agent Framework. It retrieves relevant context from Neo4j using vector, fulltext, or hybrid search, optionally enriching results through graph traversal.

## Key Design Principles

1. **No Entity Extraction** - Full message text is passed to the search index, letting Neo4j handle relevance ranking
2. **Index-Driven Configuration** - Works with any Neo4j index; configure `index_name` and `index_type`
3. **Configurable Graph Enrichment** - Custom Cypher queries traverse relationships after initial search

## Search Flow

```
invoking() called
    ↓
Filter USER/ASSISTANT messages, take recent N
    ↓
Concatenate message text (NO entity extraction)
    ↓
Execute search based on index_type:
  - vector: Embed query → db.index.vector.queryNodes()
  - fulltext: Optional stop word filtering → db.index.fulltext.queryNodes()
  - hybrid: Both vector + fulltext combined
    ↓
If mode="graph_enriched": Execute custom retrieval_query Cypher
    ↓
Format results → Return Context(messages=[...])
```

## Components

### Core Library (`packages/agent-framework-neo4j/`)

| Component | Purpose |
|-----------|---------|
| `Neo4jContextProvider` | Main provider implementing `ContextProvider` interface |
| `ProviderConfig` | Pydantic model for configuration validation |
| `ConnectionConfig` | Pydantic model for connection parameters |
| `Neo4jSettings` | Environment-based settings with Pydantic |
| `AzureAIEmbedder` | Azure AI embedding integration |
| `FulltextRetriever` | Fulltext search retriever |

### Retriever Selection

| index_type | mode | Retriever |
|------------|------|-----------|
| vector | basic | `VectorRetriever` |
| vector | graph_enriched | `VectorCypherRetriever` |
| hybrid | basic | `HybridRetriever` |
| hybrid | graph_enriched | `HybridCypherRetriever` |
| fulltext | basic/graph_enriched | `FulltextRetriever` |

## Async Design

neo4j-graphrag retrievers are synchronous. The provider wraps them with `asyncio.to_thread()` for async compatibility with the Agent Framework.

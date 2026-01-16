# API Reference

## Neo4jContextProvider

Main context provider class implementing the Microsoft Agent Framework `ContextProvider` interface.

```python
from agent_framework_neo4j import Neo4jContextProvider

provider = Neo4jContextProvider(
    uri="neo4j+s://xxx.databases.neo4j.io",
    username="neo4j",
    password="password",
    index_name="chunkEmbeddings",
    index_type="vector",  # "vector", "fulltext", or "hybrid"
    mode="basic",  # "basic" or "graph_enriched"
    top_k=5,
    embedder=my_embedder,  # Required for vector/hybrid
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uri` | `str \| None` | Neo4j connection URI. Falls back to `NEO4J_URI` env var. |
| `username` | `str \| None` | Neo4j username. Falls back to `NEO4J_USERNAME` env var. |
| `password` | `str \| None` | Neo4j password. Falls back to `NEO4J_PASSWORD` env var. |
| `index_name` | `str` | Name of the Neo4j index to query. Required. |
| `index_type` | `Literal["vector", "fulltext", "hybrid"]` | Type of search. Default: `"vector"`. |
| `fulltext_index_name` | `str \| None` | Fulltext index for hybrid search. Required for hybrid. |
| `mode` | `Literal["basic", "graph_enriched"]` | Search mode. Default: `"basic"`. |
| `retrieval_query` | `str \| None` | Cypher query for graph enrichment. Required for `graph_enriched` mode. |
| `embedder` | `Embedder \| None` | neo4j-graphrag Embedder. Required for vector/hybrid. |
| `top_k` | `int` | Number of results. Default: `5`. |
| `context_prompt` | `str` | Prompt prepended to context. |
| `message_history_count` | `int` | Recent messages to use. Default: `10`. |

## Neo4jSettings

Pydantic settings for Neo4j connection configuration.

```python
from agent_framework_neo4j import Neo4jSettings

settings = Neo4jSettings()  # Loads from environment
```

## AzureAIEmbedder

Azure AI embedder compatible with neo4j-graphrag.

```python
from azure.identity import DefaultAzureCredential
from agent_framework_neo4j import AzureAIEmbedder

embedder = AzureAIEmbedder(
    endpoint="https://your-project.models.ai.azure.com",
    credential=DefaultAzureCredential(),
    model="text-embedding-ada-002",
)
```

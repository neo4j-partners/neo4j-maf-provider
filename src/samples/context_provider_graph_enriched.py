"""
Demo: Neo4j Context Provider with Graph-Enriched Mode.

Shows semantic search using vector index combined with graph traversal
to enrich results with company, product, and risk factor context.

This demonstrates the retrieval_query pattern from neo4j-graphrag.
"""

from __future__ import annotations

import asyncio


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


# Graph-enriched retrieval query
# This query is appended after the vector search:
#   CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
#   YIELD node, score
#   <retrieval_query here>
#
# Variables available from vector search:
#   - node: The Chunk node matched by vector similarity
#   - score: Similarity score (0.0 to 1.0)
RETRIEVAL_QUERY = """
MATCH (node)-[:FROM_DOCUMENT]->(doc:Document)<-[:FILED]-(company:Company)
OPTIONAL MATCH (company)-[:FACES_RISK]->(risk:RiskFactor)
OPTIONAL MATCH (company)-[:MENTIONS]->(product:Product)
WITH node, score, company, doc,
     collect(DISTINCT risk.name)[0..5] AS risks,
     collect(DISTINCT product.name)[0..5] AS products
RETURN
    node.text AS text,
    score,
    company.name AS company,
    company.ticker AS ticker,
    risks,
    products
ORDER BY score DESC
"""


class AzureAIVectorizer:
    """
    Vectorizer using Azure AI Foundry embeddings.

    Implements VectorizerProtocol for use with Neo4jContextProvider.
    """

    def __init__(self, endpoint: str, deployment: str = "text-embedding-ada-002") -> None:
        """
        Initialize the Azure AI vectorizer.

        Args:
            endpoint: Azure AI inference endpoint (models endpoint).
            deployment: Embedding model deployment name.
        """
        from azure.ai.inference import EmbeddingsClient
        from azure.identity import DefaultAzureCredential

        self._deployment = deployment
        self._credential = DefaultAzureCredential()
        self._client = EmbeddingsClient(
            endpoint=endpoint,
            credential=self._credential,
            credential_scopes=["https://cognitiveservices.azure.com/.default"],
        )

    def _embed_sync(self, text: str) -> list[float]:
        """Synchronous embedding (internal)."""
        from azure.ai.inference.models import EmbeddingInputType

        response = self._client.embed(
            input=[text],
            model=self._deployment,
            input_type=EmbeddingInputType.QUERY,
        )
        embedding = response.data[0].embedding
        if not isinstance(embedding, list):
            raise ValueError(f"Unexpected embedding type: {type(embedding)}")
        return embedding

    def embed(self, text: str) -> list[float]:
        """Synchronously embed text into a vector."""
        return self._embed_sync(text)

    async def aembed(self, text: str) -> list[float]:
        """Asynchronously embed text into a vector."""
        return await asyncio.to_thread(self._embed_sync, text)

    def close(self) -> None:
        """Close the underlying credential and client."""
        self._credential.close()


async def demo_context_provider_graph_enriched() -> None:
    """Demo: Neo4j Context Provider with graph-enriched mode."""
    from azure.identity.aio import AzureCliCredential

    from agent import AgentConfig, create_agent_client
    from logging_config import get_logger
    from neo4j_client import Neo4jSettings
    from neo4j_provider import Neo4jContextProvider
    from vector_search import VectorSearchConfig

    logger = get_logger()

    print_header("Demo: Context Provider (Graph-Enriched Mode)")
    print("This demo shows the Neo4jContextProvider with graph-enriched mode,")
    print("combining vector search with graph traversal to provide rich context")
    print("about companies, their products, and risk factors.\n")

    # Load configs
    agent_config = AgentConfig()
    neo4j_config = Neo4jSettings()
    vector_config = VectorSearchConfig()

    if not agent_config.project_endpoint:
        print("Error: AZURE_AI_PROJECT_ENDPOINT not configured.")
        return

    if not neo4j_config.is_configured:
        print("Error: Neo4j not configured.")
        print("Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        return

    if not vector_config.is_configured:
        print("Error: Vector search not configured.")
        print("Required: AZURE_AI_PROJECT_ENDPOINT")
        return

    print(f"Agent: {agent_config.name}")
    print(f"Model: {agent_config.model}")
    print(f"Neo4j URI: {neo4j_config.uri}")
    print(f"Vector Index: {vector_config.vector_index_name}")
    print(f"Mode: graph_enriched")
    print(f"Embedding Model: {vector_config.embedding_deployment}\n")

    print("Retrieval Query Pattern:")
    print("-" * 50)
    print("  Chunk -[:FROM_DOCUMENT]-> Document <-[:FILED]- Company")
    print("  Company -[:FACES_RISK]-> RiskFactor")
    print("  Company -[:MENTIONS]-> Product")
    print("-" * 50 + "\n")

    credential = AzureCliCredential()
    vectorizer = None

    try:
        # Create vectorizer for Azure AI embeddings
        vectorizer = AzureAIVectorizer(
            endpoint=vector_config.inference_endpoint,
            deployment=vector_config.embedding_deployment,
        )
        print("Vectorizer initialized!\n")

        # Create context provider with graph-enriched mode
        provider = Neo4jContextProvider(
            uri=neo4j_config.uri,
            username=neo4j_config.username,
            password=neo4j_config.get_password(),
            index_name=vector_config.vector_index_name,
            index_type="vector",
            mode="graph_enriched",
            retrieval_query=RETRIEVAL_QUERY,
            vectorizer=vectorizer,
            top_k=5,
            context_prompt=(
                "## Graph-Enriched Knowledge Context\n"
                "The following information combines semantic search results with "
                "graph traversal to provide company, product, and risk context:"
            ),
        )

        # Create agent client
        client = create_agent_client(agent_config, credential)

        # Use both provider and agent as async context managers
        async with provider:
            print("Connected to Neo4j with graph-enriched mode!\n")

            async with client.create_agent(
                name=agent_config.name,
                instructions=(
                    "You are a helpful assistant that answers questions about companies "
                    "using graph-enriched context. Your context includes:\n"
                    "- Semantic search matches from company filings\n"
                    "- Company names and ticker symbols\n"
                    "- Products the company mentions\n"
                    "- Risk factors the company faces\n\n"
                    "When answering, cite the company, relevant products, and risks. "
                    "Be specific and reference the enriched graph data."
                ),
                context_providers=[provider],
            ) as agent:
                print("Agent created with graph-enriched context provider!\n")
                print("-" * 50)

                # Demo queries that benefit from graph enrichment
                queries = [
                    "What are Apple's main products and what risks does the company face?",
                    "Tell me about Microsoft's cloud services and business risks",
                    "What products and risks are mentioned in Amazon's filings?",
                ]

                for i, query in enumerate(queries, 1):
                    print(f"\n[Query {i}] User: {query}\n")

                    response = await agent.run(query)
                    print(f"[Query {i}] Agent: {response.text}\n")
                    print("-" * 50)

                print(
                    "\nDemo complete! Graph-enriched mode combined vector search with "
                    "graph traversal for comprehensive company context."
                )

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("Please check your Neo4j and Azure AI configuration.")
    except Exception as e:
        logger.error(f"Error during demo: {e}")
        print(f"\nError: {e}")
        raise
    finally:
        # Close vectorizer credential
        if vectorizer is not None:
            vectorizer.close()
        await credential.close()
        # Allow pending async cleanup tasks to complete
        await asyncio.sleep(0.1)

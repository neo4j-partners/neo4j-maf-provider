"""
API routes using Microsoft Agent Framework with Azure AI Foundry.

Provides REST endpoints for agent status, chat functionality, and semantic search.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

from vector_search import SemanticSearchRequest, SemanticSearchResponse

router = APIRouter()
logger = logging.getLogger("azureaiapp")

# In-memory thread storage for conversation tracking (simple demo)
# In production, use Redis or a database
_threads: dict = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.get("/agent")
async def get_agent(request: Request):
    """Return details about the current agent."""
    if not hasattr(request.app.state, "agent"):
        raise HTTPException(status_code=503, detail="Agent not initialized")

    config = request.app.state.config
    return {
        "name": config.name,
        "model": config.model,
        "instructions": config.instructions,
    }


@router.post("/chat")
async def chat(request: Request, chat_request: ChatRequest):
    """Send a message to the agent using Agent Framework with conversation tracking."""
    if not hasattr(request.app.state, "agent"):
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = request.app.state.agent

    try:
        # Get or create thread for conversation tracking
        conversation_id = chat_request.conversation_id
        if conversation_id and conversation_id in _threads:
            thread = _threads[conversation_id]
            logger.info(f"Reusing thread: conv={conversation_id[:8]}, svc_thread={thread.service_thread_id}")
        else:
            thread = agent.get_new_thread()
            conversation_id = str(uuid.uuid4())
            _threads[conversation_id] = thread
            logger.info(f"New thread: conv={conversation_id[:8]}")

        result = await agent.run(chat_request.message, thread=thread, store=False)
        logger.info(f"After run: svc_thread={thread.service_thread_id}")

        return {
            "response": result.text,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: Request, chat_request: ChatRequest):
    """Send a message to the agent with streaming response and conversation tracking."""
    if not hasattr(request.app.state, "agent"):
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent = request.app.state.agent

    try:
        # Get or create thread for conversation tracking
        conversation_id = chat_request.conversation_id
        if conversation_id and conversation_id in _threads:
            thread = _threads[conversation_id]
        else:
            thread = agent.get_new_thread()
            conversation_id = str(uuid.uuid4())
            _threads[conversation_id] = thread

        response_content = ""
        async for update in agent.run_stream(chat_request.message, thread=thread, store=False):
            if update.text:
                response_content += update.text

        return {
            "response": response_content,
            "conversation_id": conversation_id,
        }

    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(request: Request, search_request: SemanticSearchRequest):
    """
    Perform semantic search over documents with graph-aware context.

    Returns relevant document chunks enriched with company and risk factor metadata
    from the graph database.
    """
    if not hasattr(request.app.state, "vector_search_client"):
        raise HTTPException(
            status_code=503,
            detail="Vector search not initialized"
        )

    vector_search_client = request.app.state.vector_search_client
    if vector_search_client is None:
        raise HTTPException(
            status_code=503,
            detail="Vector search not configured. Check AZURE_OPENAI_* and NEO4J_* environment variables."
        )

    try:
        results = await vector_search_client.search(
            query=search_request.query,
            top_k=search_request.top_k,
        )

        return SemanticSearchResponse(
            results=results,
            query=search_request.query,
        )

    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/schema")
async def get_graph_schema(request: Request):
    """
    Return the cached graph database schema.

    Useful for understanding what data is available for queries.
    """
    if not hasattr(request.app.state, "graph_schema"):
        raise HTTPException(
            status_code=503,
            detail="Graph schema not available"
        )

    schema = request.app.state.graph_schema
    if schema is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j not configured. Graph schema unavailable."
        )

    return schema.to_dict()


# Entity search models
class EntityResult(BaseModel):
    """A single entity result."""

    id: str
    name: str


class EntityListResponse(BaseModel):
    """Response from entity listing endpoint."""

    entities: list[EntityResult]
    entity_type: str
    count: int


class RelationshipResult(BaseModel):
    """A single relationship result."""

    source: str
    source_type: str
    relationship: str
    target: str
    target_type: str


class RelationshipResponse(BaseModel):
    """Response from relationship query endpoint."""

    relationships: list[RelationshipResult]
    entity_name: str
    count: int


class EntityTypesResponse(BaseModel):
    """Response from entity types endpoint."""

    entity_types: list[str]


@router.get("/search/entities/types", response_model=EntityTypesResponse)
async def get_entity_types(request: Request):
    """
    Get the list of allowed entity types.

    Returns the entity types that can be queried (Company, Executive, Product, etc.).
    """
    if not hasattr(request.app.state, "neo4j_client") or request.app.state.neo4j_client is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j not configured. Entity search unavailable."
        )

    neo4j_client = request.app.state.neo4j_client
    entity_types = neo4j_client.get_allowed_entity_types()

    return EntityTypesResponse(entity_types=entity_types)


@router.get("/search/entities/{entity_type}", response_model=EntityListResponse)
async def list_entities(
    request: Request,
    entity_type: str,
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of entities to return"),
):
    """
    List entities of a specific type.

    Available types: Company, Executive, Product, FinancialMetric, RiskFactor, StockType, Transaction, TimePeriod.
    """
    if not hasattr(request.app.state, "neo4j_client") or request.app.state.neo4j_client is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j not configured. Entity search unavailable."
        )

    neo4j_client = request.app.state.neo4j_client

    try:
        results = await neo4j_client.list_entities_by_type(entity_type, limit=limit)

        entities = [EntityResult(id=r["id"], name=r["name"]) for r in results]
        return EntityListResponse(
            entities=entities,
            entity_type=entity_type,
            count=len(entities),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Entity list error: {e}")
        raise HTTPException(status_code=500, detail=f"Entity search failed: {str(e)}")


@router.get("/search/entities/{entity_name}/relationships", response_model=RelationshipResponse)
async def get_entity_relationships(
    request: Request,
    entity_name: str,
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of relationships to return"),
):
    """
    Get relationships for an entity by name.

    Performs a case-insensitive search for the entity name and returns its relationships.
    """
    if not hasattr(request.app.state, "neo4j_client") or request.app.state.neo4j_client is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j not configured. Entity search unavailable."
        )

    neo4j_client = request.app.state.neo4j_client

    try:
        results = await neo4j_client.get_entity_relationships(entity_name, limit=limit)

        relationships = [
            RelationshipResult(
                source=r["source"],
                source_type=r["source_type"],
                relationship=r["relationship"],
                target=r["target"],
                target_type=r["target_type"],
            )
            for r in results
        ]
        return RelationshipResponse(
            relationships=relationships,
            entity_name=entity_name,
            count=len(relationships),
        )
    except Exception as e:
        logger.error(f"Relationship query error: {e}")
        raise HTTPException(status_code=500, detail=f"Relationship query failed: {str(e)}")

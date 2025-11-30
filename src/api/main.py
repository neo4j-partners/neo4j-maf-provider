"""
FastAPI application using Microsoft Agent Framework with Azure AI Foundry.

This module sets up a FastAPI app that uses the Microsoft Agent Framework
to interact with Azure AI Foundry. It handles:
- Loading environment configuration
- Creating the agent via Agent Framework with Foundry backend
- Connecting to Neo4j and validating schema on startup
- Configuring Azure Monitor tracing (optional)
- Exposing REST endpoints for agent interaction
"""

import contextlib
import os

import fastapi
from azure.identity.aio import AzureCliCredential
from dotenv import load_dotenv

from agent import AgentConfig, create_agent_client, create_agent_context
from logging_config import configure_logging
from neo4j_client import Neo4jConfig, Neo4jClient, GraphSchema
from vector_search import VectorSearchConfig, VectorSearchClient
from util import get_env_file_path

from . import routes

logger = configure_logging(os.getenv("APP_LOG_FILE", ""))

# Tracing flag - set after environment is loaded
_tracing_enabled = False


def load_environment() -> None:
    """Load environment variables from .env file if it exists."""
    global _tracing_enabled

    env_file = get_env_file_path()
    if env_file:
        load_dotenv(env_file)
        logger.info(f"Loaded environment from: {env_file}")

    # Check if tracing is enabled
    enable_trace_str = os.getenv("ENABLE_AZURE_MONITOR_TRACING", "").lower()
    _tracing_enabled = enable_trace_str == "true"

    if _tracing_enabled:
        logger.info("Azure Monitor tracing is enabled")
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: F401
        except ModuleNotFoundError:
            logger.error("azure-monitor-opentelemetry not installed - tracing disabled")
            _tracing_enabled = False
    else:
        logger.info("Azure Monitor tracing is disabled")


async def configure_tracing(app: fastapi.FastAPI, credential: AzureCliCredential, endpoint: str) -> None:
    """
    Configure Azure Monitor tracing using the AI Project's Application Insights.

    Args:
        app: FastAPI application to store connection string
        credential: Azure credential for API access
        endpoint: Azure AI Project endpoint
    """
    if not _tracing_enabled:
        return

    try:
        from azure.ai.projects.aio import AIProjectClient
        from azure.ai.projects.telemetry import AIProjectInstrumentor
        from azure.monitor.opentelemetry import configure_azure_monitor

        async with AIProjectClient(endpoint=endpoint, credential=credential) as project_client:
            try:
                connection_string = await project_client.telemetry.get_application_insights_connection_string()
            except Exception as e:
                logger.error(f"Failed to get Application Insights connection string: {e}")
                logger.error("Enable tracing via the 'Tracing' tab in your AI Foundry project")
                return

            if not connection_string:
                logger.error("Application Insights not enabled for this project")
                logger.error("Enable it via the 'Tracing' tab in your AI Foundry project page")
                return

            configure_azure_monitor(connection_string=connection_string)
            AIProjectInstrumentor().instrument(True)
            app.state.application_insights_connection_string = connection_string
            logger.info("Azure Monitor tracing configured successfully")

    except Exception as e:
        logger.error(f"Failed to configure tracing: {e}")


async def initialize_neo4j(stack: contextlib.AsyncExitStack) -> tuple[Neo4jClient | None, GraphSchema | None]:
    """
    Initialize Neo4j connection and retrieve schema.

    Args:
        stack: AsyncExitStack to manage the client lifecycle.

    Returns:
        Tuple of (Neo4jClient, GraphSchema) if successful, (None, None) if not configured
        or connection fails.
    """
    neo4j_config = Neo4jConfig()

    if not neo4j_config.is_configured:
        logger.info("Neo4j not configured - graph features disabled")
        return None, None

    try:
        neo4j_client = Neo4jClient(neo4j_config)
        await stack.enter_async_context(neo4j_client)

        # Fetch schema to validate connection
        schema = await neo4j_client.get_schema()
        logger.info(f"Neo4j initialized - {schema.summary()}")

        # Log detailed schema info
        if schema.node_labels:
            logger.info(f"  Node labels: {', '.join(schema.node_labels)}")
        if schema.relationship_types:
            logger.info(f"  Relationship types: {', '.join(schema.relationship_types)}")

        return neo4j_client, schema

    except ConnectionError as e:
        logger.warning(f"Neo4j connection failed: {e}")
        logger.warning("Continuing without Neo4j - graph features disabled")
        return None, None
    except Exception as e:
        logger.warning(f"Neo4j initialization failed: {e}")
        logger.warning("Continuing without Neo4j - graph features disabled")
        return None, None


def initialize_vector_search(neo4j_client: Neo4jClient | None) -> VectorSearchClient | None:
    """
    Initialize vector search client if configured.

    Args:
        neo4j_client: Connected Neo4j client (required for vector search).

    Returns:
        VectorSearchClient if configured, None otherwise.
    """
    if neo4j_client is None:
        logger.info("Vector search disabled - Neo4j not available")
        return None

    vector_config = VectorSearchConfig()

    if not vector_config.is_configured:
        logger.info("Vector search not configured - AZURE_OPENAI_* variables not set")
        return None

    try:
        client = VectorSearchClient(vector_config, neo4j_client)
        logger.info(f"Vector search initialized with index '{vector_config.vector_index_name}'")
        return client
    except ValueError as e:
        logger.warning(f"Vector search configuration error: {e}")
        return None
    except Exception as e:
        logger.warning(f"Vector search initialization failed: {e}")
        return None


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    """
    FastAPI lifespan manager for startup and shutdown.

    On startup:
    - Loads environment variables
    - Creates Azure CLI credential
    - Creates AzureAIClient (V2)
    - Creates the AI agent (persistent in Foundry)
    - Connects to Neo4j and validates schema (optional)

    On shutdown:
    - Cleans up credential, client, and Neo4j resources
    """
    load_environment()
    config = AgentConfig()

    if not config.project_endpoint:
        logger.error("Missing required environment variable: AZURE_AI_PROJECT_ENDPOINT")
        yield
        return

    # Use AsyncExitStack to manage multiple async context managers
    async with contextlib.AsyncExitStack() as stack:
        # Enter credential context
        credential = await stack.enter_async_context(AzureCliCredential())

        # Configure Azure Monitor tracing (if enabled)
        await configure_tracing(app, credential, config.project_endpoint)

        # Create client and enter agent context
        client = create_agent_client(config, credential)
        agent = await stack.enter_async_context(create_agent_context(client, config))

        app.state.agent = agent
        app.state.config = config
        logger.info(f"Agent initialized: {config.name}")

        # Initialize Neo4j (optional - app works without it)
        neo4j_client, schema = await initialize_neo4j(stack)
        app.state.neo4j_client = neo4j_client
        app.state.graph_schema = schema

        # Initialize vector search (requires Neo4j and Azure OpenAI)
        vector_search_client = initialize_vector_search(neo4j_client)
        app.state.vector_search_client = vector_search_client

        yield


def create_app() -> fastapi.FastAPI:
    """Create and configure the FastAPI application."""
    app = fastapi.FastAPI(lifespan=lifespan)
    app.include_router(routes.router)
    return app

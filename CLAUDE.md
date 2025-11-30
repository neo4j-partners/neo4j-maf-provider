# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Guidelines

- When proposing new features, write proposals in plain English only (no code). Keep proposals simple—this is a demo project.
- Use Python best practices and pydantic type safety where possible.
- **Always use the latest version of the Microsoft Agent Framework with Azure AI Foundry** for agent-related functionality. Reference the framework source at `/Users/ryanknight/projects/azure/agent-framework` and samples at `/Users/ryanknight/projects/azure/Agent-Framework-Samples`. See `AGENT_FRAMEWORK.md` for details.

## Project Overview

This is an Azure AI Agent Service API built with FastAPI using the **Microsoft Agent Framework (2025)** with **Azure AI Foundry** integration. It uses `AzureAIAgentClient` for persistent, service-managed agents hosted in Azure AI Foundry, exposing REST endpoints for agent status and chat.

## Commands

### Setup
```bash
azd up                    # Provision Azure infrastructure
uv sync --prerelease=allow # Install dependencies (pre-release required for Agent Framework)
uv run setup_env.py       # Pull env vars from azd into .env (project root)
```

### Run Locally
```bash
uv run uvicorn api.main:create_app --factory --reload
```

### Docker
```bash
docker build -t simple-ai-agents .
docker run -p 8000:50505 --env-file .env simple-ai-agents
```

## Architecture

### Application Flow
1. `api/main.py` - FastAPI app factory with lifespan manager that:
   - Loads environment from `.env` in project root (via `util.get_env_file_path()`)
   - Creates an `AzureAIAgentClient` connected to Azure AI Foundry
   - Creates a persistent agent via `create_agent()` context manager

2. `agent.py` - Agent management using Agent Framework:
   - `AgentConfig` (pydantic-settings) for configuration
   - `create_agent_client()` creates `AzureAIAgentClient` with Azure CLI credentials
   - `create_agent_context()` returns async context manager for agent lifecycle

3. `api/routes.py` - Three endpoints:
   - `GET /agent` - Returns agent metadata
   - `POST /chat` - Chat using Agent Framework's `run()` method
   - `POST /chat/stream` - Streaming chat using `run_stream()` method

### Production (Gunicorn)
`gunicorn.conf.py` validates environment on startup. Each worker creates its own agent instance backed by Azure AI Foundry.

## Environment Variables

Required:
- `AZURE_AI_PROJECT_ENDPOINT` - Azure AI Foundry project endpoint

Optional:
- `AZURE_AI_AGENT_NAME` - Agent name (default: "arches-agent")
- `AZURE_AI_MODEL_NAME` - Model deployment name
- `AZURE_AI_EMBEDDING_NAME` - Embedding model deployment name
- `APP_LOG_FILE` - Log file path

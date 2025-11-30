# Neo4j MAF Sample Provider

A sample AI agent API built with Neo4j GraphRAG and the **Microsoft Agent Framework (2025)** with **Azure AI Foundry**.

This repository provides a production-ready FastAPI application exposing REST endpoints for agent status, chat, and streaming chat, using `AzureAIAgentClient` for persistent agents hosted in Azure AI Foundry.

## Quick Start

For GitHub Codespaces or Local Dev Container setup, see **[GUIDE_DEV_CONTAINERS.md](GUIDE_DEV_CONTAINERS.md)**.

## Prerequisites (Manual Setup)

*   **[uv](https://github.com/astral-sh/uv):** An extremely fast Python package installer and resolver.
*   **[Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd):** For infrastructure provisioning (`azd login`).
*   **[Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli):** For authentication (`az login`).
*   **Git**

## Getting Started

### 1. Configure Azure Region
Run the setup script to select your Azure region and initialize the environment:

```bash
./scripts/setup_azure.sh
```

> **Note:** This script clears the `.azure/` directory and Azure-related settings from `.env` to ensure `azd up` creates a fresh environment. Neo4j settings in `.env` are preserved. See [docs/AZ_CLI_GUIDE.md](docs/AZ_CLI_GUIDE.md) for details on environment management.

> **Supported Regions:** `eastus2`, `swedencentral`, or `westus2`

### 2. Provision Infrastructure
Deploy the Azure AI resources:

```bash
azd up
```

> **Note:** This creates an Azure AI Foundry project with two model deployments: **gpt-4o** (for chat completions) and **text-embedding-ada-002** (for vector embeddings). Open [ai.azure.com](https://ai.azure.com/) in the same browser where you're logged into Azure to view your project. See [docs/FOUNDRY_GUIDE.md](docs/FOUNDRY_GUIDE.md) for more details.

> **Note:** For full deployment options (including Container App), see [docs/AZURE_DEPLOY_GUIDE.md](docs/AZURE_DEPLOY_GUIDE.md).

### 3. Install Dependencies
Use `uv` to sync dependencies defined in `pyproject.toml`.

```bash
uv sync --prerelease=allow
```

### 4. Setup Environment Variables
Run the helper script to pull environment variables from `azd` and create a local `.env` file.

```bash
uv run setup_env.py
```

### 5. Restore Neo4j Database (Optional)

> **Note:** If you're using a pre-provisioned Neo4j database, this step is not needed—the data is already loaded.

To restore the financial graph data to your own Neo4j instance:

```bash
uv run python scripts/restore_neo4j.py
```

This streams and restores the backup from GitHub, creating:
- **Nodes:** `AssetManager`, `Company`, `Document`, `Chunk`
- **Relationships:** `OWNS`, `FILED`, `HAS_CHUNK`

The script reads Neo4j credentials (`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`) from `.env` automatically.

### 6. Build and Deploy Agents to Azure AI Foundry

**Interactive Agent (CLI)**
Run the agent directly in your terminal for interactive chat:

```bash
uv run start-agent
```

Type your messages and press Enter to chat. Type `quit` or `exit` to end the session.

**AI Agent API Server**
Run the AI agent API server with Neo4j GraphRAG integration:

```bash
uv run uvicorn api.main:create_app --factory --reload
```

The API will be available at `http://localhost:8000`.

## Testing the AI Agent API

Run all tests to verify the AI agent endpoints are working:

```bash
uv run python src/test_server.py all
```

For individual test options and API endpoint details, see [docs/SERVER_OVERVIEW.md](docs/SERVER_OVERVIEW.md).

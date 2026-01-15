# Proposal: Neo4j Context Provider as a PyPI Library

## Key Goals

- **ALWAYS FIX THE CORE ISSUE!**
- **COMPLETE CHANGE**: All occurrences must be changed in a single, atomic update
- **CLEAN IMPLEMENTATION**: Simple, direct replacements only
- **NO MIGRATION PHASES**: Do not create temporary compatibility periods
- **NO ROLLBACK PLANS**: Never create rollback plans
- **NO PARTIAL UPDATES**: Change everything or change nothing
- **NO COMPATIBILITY LAYERS**: Do not maintain old and new paths simultaneously
- **NO BACKUPS OF OLD CODE**: Do not comment out old code "just in case"
- **NO CODE DUPLICATION**: Do not duplicate functions to handle both patterns
- **NO WRAPPER FUNCTIONS**: Direct replacements only, no abstraction layers
- **DO NOT CALL FUNCTIONS ENHANCED OR IMPROVED**: Update the actual methods directly
- **USE MODULES AND CLEAN CODE!**

---

## Executive Summary

Restructure `neo4j-maf-provider` into a **uv workspace monorepo** with two packages:
1. `agent-framework-neo4j` - The publishable PyPI library
2. `neo4j-provider-samples` - Demo applications that depend on the library

This is a complete cut-over. The old structure is deleted entirely and replaced with the new structure in a single atomic change.

---

## Package Naming

Following the Microsoft Agent Framework ecosystem conventions:

| Element | Value |
|---------|-------|
| **PyPI package name** | `agent-framework-neo4j` |
| **Python module name** | `agent_framework_neo4j` |
| **Primary export** | `Neo4jContextProvider` |
| **Settings class** | `Neo4jSettings` |

---

## New Structure (UV Workspaces Monorepo)

```
neo4j-maf-provider/
├── pyproject.toml                           # Workspace root
├── README.md                                # Repository overview
├── CLAUDE.md                                # Claude Code instructions
├── LICENSE
│
├── packages/
│   └── agent-framework-neo4j/               # Publishable PyPI package
│       ├── pyproject.toml
│       ├── README.md
│       └── src/
│           └── agent_framework_neo4j/
│               ├── __init__.py              # Public API exports
│               ├── _provider.py             # Neo4jContextProvider
│               ├── _settings.py             # Neo4jSettings, AzureAISettings
│               ├── _embedder.py             # AzureAIEmbedder
│               ├── _fulltext.py             # FulltextRetriever
│               └── _stop_words.py           # Stop word list
│
├── samples/                                 # Demo applications
│   ├── pyproject.toml                       # Depends on agent-framework-neo4j
│   ├── README.md
│   │
│   ├── basic_fulltext/
│   │   ├── main.py
│   │   └── README.md
│   │
│   ├── vector_search/
│   │   ├── main.py
│   │   └── README.md
│   │
│   ├── graph_enriched/
│   │   ├── main.py
│   │   └── README.md
│   │
│   ├── aircraft_domain/
│   │   ├── maintenance_search.py
│   │   ├── flight_delays.py
│   │   ├── component_health.py
│   │   └── README.md
│   │
│   └── shared/
│       ├── __init__.py
│       ├── agent.py                         # Agent setup helpers
│       ├── env.py                           # Environment loading
│       └── logging.py                       # Logging configuration
│
├── tests/                                   # Library tests
│   ├── conftest.py
│   ├── test_provider.py
│   ├── test_settings.py
│   └── test_fulltext.py
│
├── infra/                                   # Azure infrastructure (unchanged)
│   ├── main.bicep
│   └── ...
│
└── docs/                                    # Documentation
    ├── getting_started.md
    ├── api_reference.md
    └── architecture.md
```

---

## Root `pyproject.toml` (Workspace Configuration)

```toml
[project]
name = "neo4j-maf-provider-workspace"
version = "0.1.0"
description = "Neo4j Context Provider workspace"
requires-python = ">=3.10"

[tool.uv.workspace]
members = [
    "packages/agent-framework-neo4j",
    "samples",
]

[tool.uv.sources]
agent-framework-neo4j = { workspace = true }

[tool.uv]
prerelease = "if-necessary-or-explicit"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"

[tool.ruff]
line-length = 120
target-version = "py310"
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
]

[tool.ruff.isort]
known-first-party = ["agent_framework_neo4j"]

[tool.mypy]
python_version = "3.10"
strict = true
plugins = ["pydantic.mypy"]

[tool.coverage.run]
source = ["packages/agent-framework-neo4j/src/agent_framework_neo4j"]
branch = true
```

---

## Library Package `pyproject.toml`

**Location**: `packages/agent-framework-neo4j/pyproject.toml`

```toml
[project]
name = "agent-framework-neo4j"
version = "0.1.0"
description = "Neo4j Context Provider for Microsoft Agent Framework - RAG with knowledge graphs"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
authors = [
    { name = "Your Name", email = "your.email@example.com" }
]
keywords = [
    "neo4j",
    "knowledge-graph",
    "rag",
    "context-provider",
    "agent-framework",
    "llm",
    "vector-search",
    "graph-database",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
    "Topic :: Database",
    "Typing :: Typed",
]

dependencies = [
    "agent-framework-core>=1.0.0b",
    "neo4j>=5.0.0",
    "neo4j-graphrag>=1.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
azure = [
    "azure-identity>=1.19.0",
    "azure-ai-inference>=1.0.0b7",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=6.0.0",
    "mypy>=1.10.0",
    "ruff>=0.4.0",
]

[project.urls]
Homepage = "https://github.com/yourorg/neo4j-maf-provider"
Repository = "https://github.com/yourorg/neo4j-maf-provider"
Issues = "https://github.com/yourorg/neo4j-maf-provider/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_framework_neo4j"]
```

---

## Samples Package `pyproject.toml`

**Location**: `samples/pyproject.toml`

```toml
[project]
name = "neo4j-provider-samples"
version = "0.1.0"
description = "Sample applications for agent-framework-neo4j"
requires-python = ">=3.10"
dependencies = [
    "agent-framework-neo4j[azure]",
    "agent-framework-azure-ai>=1.0.0b",
    "python-dotenv",
]

[project.scripts]
start-samples = "shared.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["shared"]
```

---

## Library Public API

**Location**: `packages/agent-framework-neo4j/src/agent_framework_neo4j/__init__.py`

```python
"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j knowledge graphs using vector,
fulltext, or hybrid search with optional graph enrichment.
"""

from ._provider import Neo4jContextProvider
from ._settings import Neo4jSettings, AzureAISettings
from ._embedder import AzureAIEmbedder
from ._fulltext import FulltextRetriever

__version__ = "0.1.0"

__all__ = [
    "Neo4jContextProvider",
    "Neo4jSettings",
    "AzureAISettings",
    "AzureAIEmbedder",
    "FulltextRetriever",
    "__version__",
]
```

---

## File Mapping (Old → New)

| Old Location | New Location |
|--------------|--------------|
| `src/neo4j_provider/provider.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/_provider.py` |
| `src/neo4j_provider/settings.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/_settings.py` |
| `src/neo4j_provider/embedder.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/_embedder.py` |
| `src/neo4j_provider/fulltext.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/_fulltext.py` |
| `src/neo4j_provider/stop_words.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/_stop_words.py` |
| `src/neo4j_provider/__init__.py` | `packages/agent-framework-neo4j/src/agent_framework_neo4j/__init__.py` |
| `src/samples/context_provider_basic.py` | `samples/basic_fulltext/main.py` |
| `src/samples/context_provider_vector.py` | `samples/vector_search/main.py` |
| `src/samples/context_provider_graph_enriched.py` | `samples/graph_enriched/main.py` |
| `src/samples/aircraft_maintenance_search.py` | `samples/aircraft_domain/maintenance_search.py` |
| `src/samples/aircraft_flight_delays.py` | `samples/aircraft_domain/flight_delays.py` |
| `src/samples/component_health.py` | `samples/aircraft_domain/component_health.py` |
| `src/samples/semantic_search.py` | `samples/vector_search/semantic_search.py` |
| `src/samples/azure_thread_memory.py` | `samples/basic_fulltext/azure_thread_memory.py` |
| `src/samples/_utils.py` | `samples/shared/utils.py` |
| `src/utils/env.py` | `samples/shared/env.py` |
| `src/utils/logging.py` | `samples/shared/logging.py` |
| `src/agent.py` | `samples/shared/agent.py` |
| `src/main.py` | `samples/shared/cli.py` |
| `tests/test_provider.py` | `tests/test_provider.py` |

---

## Files to Delete

These files and directories are removed entirely:

- `src/` (entire directory - contents moved to new locations)
- `src/__init__.py`
- `src/neo4j_provider/` (moved to `packages/agent-framework-neo4j/`)
- `src/samples/` (moved to `samples/`)
- `src/utils/` (moved to `samples/shared/`)

---

## Import Changes

All imports change from the old module name to the new module name:

| Old Import | New Import |
|------------|------------|
| `from neo4j_provider import Neo4jContextProvider` | `from agent_framework_neo4j import Neo4jContextProvider` |
| `from neo4j_provider import Neo4jSettings` | `from agent_framework_neo4j import Neo4jSettings` |
| `from neo4j_provider import AzureAISettings` | `from agent_framework_neo4j import AzureAISettings` |
| `from neo4j_provider import AzureAIEmbedder` | `from agent_framework_neo4j import AzureAIEmbedder` |
| `from neo4j_provider import FulltextRetriever` | `from agent_framework_neo4j import FulltextRetriever` |
| `from neo4j_provider.fulltext import FulltextRetriever` | `from agent_framework_neo4j import FulltextRetriever` |
| `from neo4j_provider.settings import Neo4jSettings` | `from agent_framework_neo4j import Neo4jSettings` |

Internal imports within the library change:

| Old Internal Import | New Internal Import |
|---------------------|---------------------|
| `from neo4j_provider.fulltext import FulltextRetriever` | `from agent_framework_neo4j._fulltext import FulltextRetriever` |
| `from neo4j_provider.settings import Neo4jSettings` | `from agent_framework_neo4j._settings import Neo4jSettings` |

---

## Sample Structure

### `samples/basic_fulltext/main.py`

```python
"""Basic fulltext search with Neo4j Context Provider."""

import asyncio

from dotenv import load_dotenv

from agent_framework_neo4j import Neo4jContextProvider, Neo4jSettings

load_dotenv()


async def main() -> None:
    settings = Neo4jSettings()

    provider = Neo4jContextProvider(
        uri=settings.uri,
        username=settings.username,
        password=settings.get_password(),
        index_name=settings.fulltext_index_name,
        index_type="fulltext",
    )

    async with provider:
        # Demo implementation
        pass


if __name__ == "__main__":
    asyncio.run(main())
```

### `samples/shared/cli.py`

```python
"""Interactive CLI for running samples."""

import sys
from samples.basic_fulltext import main as basic_main
from samples.vector_search import main as vector_main
from samples.graph_enriched import main as graph_main


SAMPLES = {
    "1": ("Basic Fulltext Search", basic_main),
    "2": ("Vector Search", vector_main),
    "3": ("Graph Enriched", graph_main),
}


def main() -> None:
    if len(sys.argv) > 1:
        choice = sys.argv[1]
        if choice in SAMPLES:
            _, sample_main = SAMPLES[choice]
            sample_main.main()
            return

    print("Available samples:")
    for key, (name, _) in SAMPLES.items():
        print(f"  {key}: {name}")

    choice = input("\nSelect sample: ").strip()
    if choice in SAMPLES:
        _, sample_main = SAMPLES[choice]
        sample_main.main()


if __name__ == "__main__":
    main()
```

---

## Commands

### Setup

```bash
# Install all workspace packages in development mode
uv sync --prerelease=allow

# Install only the library
uv sync --package agent-framework-neo4j --prerelease=allow

# Install library with Azure extras
uv sync --package agent-framework-neo4j --extra azure --prerelease=allow
```

### Run Samples

```bash
# Interactive menu
uv run start-samples

# Run specific sample
uv run python samples/basic_fulltext/main.py
uv run python samples/vector_search/main.py
uv run python samples/graph_enriched/main.py
```

### Development

```bash
# Run tests
uv run pytest

# Type checking
uv run mypy packages/agent-framework-neo4j/src/agent_framework_neo4j

# Linting
uv run ruff check packages/agent-framework-neo4j/src
uv run ruff format packages/agent-framework-neo4j/src
```

### Build and Publish

```bash
# Build the library package
uv build --package agent-framework-neo4j

# Publish to PyPI
uv publish --package agent-framework-neo4j
```

---

## Test Configuration

**Location**: `tests/conftest.py`

```python
"""Shared test fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for unit tests."""
    driver = MagicMock()
    driver.verify_connectivity = MagicMock()
    driver.close = MagicMock()
    return driver


@pytest.fixture
def mock_embedder():
    """Mock embedder for unit tests."""
    embedder = MagicMock()
    embedder.embed_query = MagicMock(return_value=[0.1] * 1536)
    return embedder
```

---

## Library README

**Location**: `packages/agent-framework-neo4j/README.md`

```markdown
# agent-framework-neo4j

Neo4j Context Provider for Microsoft Agent Framework - RAG with knowledge graphs.

## Installation

```bash
pip install agent-framework-neo4j

# With Azure AI embeddings
pip install agent-framework-neo4j[azure]
```

## Quick Start

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

## Features

- Vector, fulltext, and hybrid search modes
- Graph-enriched retrieval with custom Cypher queries
- Configurable message history windowing
- Pydantic settings for environment-based configuration
- Compatible with neo4j-graphrag retrievers

## Environment Variables

```
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_VECTOR_INDEX_NAME=chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME=search_chunks
```

## License

MIT
```

---

## Repository README

**Location**: `README.md` (root)

```markdown
# neo4j-maf-provider

Monorepo containing the Neo4j Context Provider for Microsoft Agent Framework.

## Structure

- `packages/agent-framework-neo4j/` - Publishable PyPI library
- `samples/` - Demo applications
- `tests/` - Library tests
- `infra/` - Azure infrastructure

## Quick Start

```bash
# Setup
uv sync --prerelease=allow

# Run samples
uv run start-samples

# Run tests
uv run pytest
```

## Publishing

```bash
uv build --package agent-framework-neo4j
uv publish --package agent-framework-neo4j
```
```

---

## Summary

| Aspect | Value |
|--------|-------|
| **Structure** | UV workspaces monorepo |
| **Library package** | `packages/agent-framework-neo4j/` |
| **Samples package** | `samples/` |
| **Module name** | `agent_framework_neo4j` |
| **Internal file prefix** | Underscore (`_provider.py`) |
| **Build backend** | Hatchling |
| **Test runner** | pytest with asyncio |

This is a complete cut-over. Execute all changes atomically.

---

## References

- [Python Packaging User Guide - src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [UV Workspaces Documentation](https://docs.astral.sh/uv/concepts/workspaces/)
- [Writing pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)

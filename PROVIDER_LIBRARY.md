# Proposal: Neo4j Context Provider as a PyPI Library

This document proposes how to restructure the `neo4j-maf-provider` project into a publishable PyPI library, separating the core provider from demo/sample code.

## Executive Summary

The current repository mixes library code (`neo4j_provider/`) with demo applications (`samples/`), Azure infrastructure (`infra/`), and application-specific utilities (`agent.py`, `main.py`). To publish as a PyPI package, we need to:

1. **Separate concerns**: Extract the core provider into a standalone, installable package
2. **Follow framework conventions**: Align naming and structure with the Microsoft Agent Framework ecosystem
3. **Move demos to a separate repository or directory**: Keep samples as examples that depend on the published package
4. **Add proper library metadata**: Classifiers, documentation, versioning, and quality tooling

---

## Proposed Package Name and Namespace

Following the Microsoft Agent Framework naming convention observed in the ecosystem:

| Element | Value |
|---------|-------|
| **PyPI package name** | `agent-framework-neo4j` |
| **Python module name** | `agent_framework_neo4j` |
| **Primary export** | `Neo4jContextProvider` |
| **Settings class** | `Neo4jSettings` |

This follows the pattern established by `agent-framework-redis`, `agent-framework-azure-ai-search`, and `agent-framework-mem0`.

---

## Current vs Proposed Structure

### Current Structure

```
neo4j-maf-provider/
├── src/
│   ├── neo4j_provider/           # Core library code (should be package)
│   │   ├── __init__.py
│   │   ├── provider.py           # Main provider implementation
│   │   ├── settings.py           # Pydantic settings
│   │   ├── embedder.py           # Azure AI embedder
│   │   ├── fulltext.py           # Fulltext retriever
│   │   └── stop_words.py         # Stop word list
│   │
│   ├── samples/                   # Demo applications (should be separate)
│   │   ├── azure_thread_memory.py
│   │   ├── semantic_search.py
│   │   ├── context_provider_*.py
│   │   ├── aircraft_*.py
│   │   └── component_health.py
│   │
│   ├── utils/                     # Shared utilities (application-specific)
│   │   ├── env.py
│   │   └── logging.py
│   │
│   ├── agent.py                   # Demo agent setup (application-specific)
│   └── main.py                    # Demo CLI entry point (application-specific)
│
├── infra/                         # Azure infrastructure (not for library)
├── tests/                         # Test suite (keep with library)
└── pyproject.toml                 # Mixed package + app config
```

### Proposed Structure: Monorepo with Workspaces

The cleanest approach uses a **monorepo with uv workspaces**, allowing the library and samples to coexist while maintaining clear separation:

```
neo4j-maf-provider/
├── packages/
│   └── agent-framework-neo4j/          # Publishable PyPI package
│       ├── agent_framework_neo4j/
│       │   ├── __init__.py             # Public API exports
│       │   ├── _provider.py            # Neo4jContextProvider
│       │   ├── _settings.py            # Neo4jSettings, AzureAISettings
│       │   ├── _embedder.py            # AzureAIEmbedder
│       │   ├── _fulltext.py            # FulltextRetriever
│       │   └── _stop_words.py          # Stop word list
│       ├── tests/
│       │   ├── conftest.py
│       │   ├── test_provider.py
│       │   ├── test_settings.py
│       │   └── test_fulltext.py
│       ├── pyproject.toml              # Library-only dependencies
│       ├── README.md                   # Library documentation
│       └── LICENSE
│
├── samples/                             # Demo applications (separate project)
│   ├── 01_basic_fulltext/
│   │   ├── main.py
│   │   ├── .env.example
│   │   └── README.md
│   ├── 02_vector_search/
│   │   ├── main.py
│   │   ├── .env.example
│   │   └── README.md
│   ├── 03_graph_enriched/
│   │   ├── main.py
│   │   ├── .env.example
│   │   └── README.md
│   ├── 04_aircraft_domain/
│   │   ├── maintenance_search.py
│   │   ├── flight_delays.py
│   │   ├── component_health.py
│   │   ├── .env.example
│   │   └── README.md
│   ├── shared/                          # Shared utilities for samples
│   │   ├── __init__.py
│   │   ├── agent.py                     # Agent setup helpers
│   │   ├── logging.py                   # Logging configuration
│   │   └── env.py                       # Environment loading
│   ├── pyproject.toml                   # Sample-specific dependencies
│   └── README.md                        # Samples overview
│
├── infra/                               # Azure infrastructure (unchanged)
│   ├── main.bicep
│   └── ...
│
├── docs/                                # Documentation site (optional)
│   ├── getting_started.md
│   ├── api_reference.md
│   ├── architecture.md
│   └── examples.md
│
├── pyproject.toml                       # Workspace root configuration
├── README.md                            # Repository overview
├── CLAUDE.md                            # Claude Code instructions
└── LICENSE
```

---

## Alternative Structure: Flat Single-Package Layout

For simpler maintenance, a flat structure with the library at root level is also viable:

```
neo4j-maf-provider/
├── src/
│   └── agent_framework_neo4j/          # Renamed from neo4j_provider
│       ├── __init__.py
│       ├── _provider.py
│       ├── _settings.py
│       ├── _embedder.py
│       ├── _fulltext.py
│       └── _stop_words.py
│
├── samples/                             # Demos (not installed)
│   └── ... (same as above)
│
├── tests/
│   └── ...
│
├── docs/
│   └── ...
│
├── infra/
│   └── ...
│
├── pyproject.toml                       # Single package config
├── README.md
└── LICENSE
```

**Recommendation**: Start with the flat single-package layout for simplicity. Migrate to monorepo only if multiple packages emerge (e.g., `agent-framework-neo4j-graphrag` for advanced graph features).

---

## Package Configuration

### Library `pyproject.toml`

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

# Minimal dependencies for core functionality
dependencies = [
    "agent-framework-core>=1.0.0b",
    "neo4j>=5.0.0",
    "neo4j-graphrag>=1.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]

[project.optional-dependencies]
# Azure AI embeddings support
azure = [
    "azure-identity>=1.19.0",
    "azure-ai-inference>=1.0.0b7",
]
# Development dependencies
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=6.0.0",
    "mypy>=1.10.0",
    "ruff>=0.4.0",
]
# Documentation
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.0.0",
    "mkdocstrings[python]>=0.25.0",
]
# All optional dependencies
all = [
    "agent-framework-neo4j[azure,dev,docs]",
]

[project.urls]
Homepage = "https://github.com/yourorg/agent-framework-neo4j"
Documentation = "https://yourorg.github.io/agent-framework-neo4j"
Repository = "https://github.com/yourorg/agent-framework-neo4j"
Issues = "https://github.com/yourorg/agent-framework-neo4j/issues"
Changelog = "https://github.com/yourorg/agent-framework-neo4j/blob/main/CHANGELOG.md"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_framework_neo4j"]

[tool.hatch.build.targets.sdist]
include = [
    "/src",
    "/tests",
    "/README.md",
    "/LICENSE",
]

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
ignore = [
    "E501",   # line too long (handled by formatter)
]

[tool.ruff.isort]
known-first-party = ["agent_framework_neo4j"]

[tool.mypy]
python_version = "3.10"
strict = true
plugins = ["pydantic.mypy"]

[tool.coverage.run]
source = ["agent_framework_neo4j"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

### Samples `pyproject.toml`

```toml
[project]
name = "neo4j-provider-samples"
version = "0.1.0"
description = "Sample applications demonstrating agent-framework-neo4j"
requires-python = ">=3.10"
dependencies = [
    "agent-framework-neo4j[azure]",    # Install from PyPI
    "agent-framework-azure-ai>=1.0.0b",
    "python-dotenv",
]

[project.scripts]
run-samples = "shared.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Library Module Structure

### Public API (`__init__.py`)

The library should export a clean, minimal public API:

```python
"""
Neo4j Context Provider for Microsoft Agent Framework.

Provides RAG context from Neo4j knowledge graphs using vector,
fulltext, or hybrid search with optional graph enrichment.

Example:
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
        # Use with agent
        pass
"""

from ._provider import Neo4jContextProvider
from ._settings import Neo4jSettings, AzureAISettings
from ._embedder import AzureAIEmbedder
from ._fulltext import FulltextRetriever

__version__ = "0.1.0"

__all__ = [
    # Core provider
    "Neo4jContextProvider",
    # Configuration
    "Neo4jSettings",
    "AzureAISettings",
    # Utilities
    "AzureAIEmbedder",
    "FulltextRetriever",
    # Version
    "__version__",
]
```

### Internal Modules (Prefixed with Underscore)

Following the Agent Framework pattern, internal implementation files use underscore prefix:

- `_provider.py` - Main `Neo4jContextProvider` class
- `_settings.py` - `Neo4jSettings` and `AzureAISettings` Pydantic models
- `_embedder.py` - `AzureAIEmbedder` implementation
- `_fulltext.py` - `FulltextRetriever` for fulltext-only search
- `_stop_words.py` - Stop word list for fulltext filtering

This convention signals that direct imports from these modules are not part of the public API and may change without notice.

---

## Sample Organization

### Progressive Complexity

Organize samples by increasing complexity, numbered for clear progression:

| Sample | Description | Index Type | Mode | Features |
|--------|-------------|------------|------|----------|
| `01_basic_fulltext/` | Simplest fulltext search | fulltext | basic | Stop word filtering |
| `02_vector_search/` | Vector similarity search | vector | basic | Azure AI embeddings |
| `03_graph_enriched/` | Graph traversal context | vector | graph_enriched | Custom Cypher queries |
| `04_aircraft_domain/` | Domain-specific examples | mixed | mixed | Multiple query patterns |

### Sample Template

Each sample directory follows a consistent structure:

```
01_basic_fulltext/
├── main.py              # Entry point with argparse
├── .env.example         # Required environment variables
└── README.md            # Setup instructions, expected output
```

**`main.py` Pattern:**

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

### Shared Sample Utilities

The `samples/shared/` directory contains utilities that are specific to running demos but not part of the library:

- **`agent.py`** - Helper functions for creating agents with the provider
- **`logging.py`** - Consistent logging setup across samples
- **`env.py`** - Environment file discovery and loading
- **`cli.py`** - Interactive menu for selecting samples

---

## Migration Steps

### Phase 1: Rename and Restructure (Non-Breaking)

1. **Rename module directory**
   - `src/neo4j_provider/` → `src/agent_framework_neo4j/`

2. **Prefix internal files**
   - `provider.py` → `_provider.py`
   - `settings.py` → `_settings.py`
   - `embedder.py` → `_embedder.py`
   - `fulltext.py` → `_fulltext.py`
   - `stop_words.py` → `_stop_words.py`

3. **Update imports throughout codebase**
   - Update all `from neo4j_provider import ...` to `from agent_framework_neo4j import ...`

4. **Move application code**
   - `src/samples/` → `samples/` (top-level)
   - `src/utils/` → `samples/shared/`
   - `src/agent.py` → `samples/shared/agent.py`
   - `src/main.py` → `samples/shared/cli.py`
   - Delete `src/__init__.py` (not needed for src layout)

### Phase 2: Update Configuration

1. **Split `pyproject.toml`**
   - Create library-focused `pyproject.toml` at root
   - Create `samples/pyproject.toml` for demo dependencies

2. **Update build configuration**
   - Remove samples from wheel package list
   - Update `[tool.hatch.build.targets.wheel]` to only include library

3. **Add library metadata**
   - Classifiers, keywords, URLs
   - License file reference

### Phase 3: Documentation and Quality

1. **Update README.md**
   - Focus on library usage (installation, quick start, API)
   - Move sample details to `samples/README.md`

2. **Add API documentation**
   - Docstrings on all public classes and methods
   - Consider MkDocs for hosted documentation

3. **Add quality tooling**
   - Pre-commit hooks for ruff, mypy
   - GitHub Actions for CI/CD
   - Coverage reporting

### Phase 4: Publishing

1. **Choose repository location**
   - Option A: Keep in current repo, publish library subdirectory
   - Option B: Create new `agent-framework-neo4j` repository

2. **Set up PyPI publishing**
   - Create PyPI account and API token
   - Configure GitHub Actions for automated releases
   - Use semantic versioning with `bumpversion` or similar

3. **Test installation**
   - `pip install agent-framework-neo4j`
   - Verify all exports work correctly
   - Test samples with installed package

---

## Dependency Considerations

### Core vs Optional Dependencies

| Dependency | Category | Rationale |
|------------|----------|-----------|
| `agent-framework-core` | Core | Required for ContextProvider interface |
| `neo4j` | Core | Required for database connection |
| `neo4j-graphrag` | Core | Required for retriever implementations |
| `pydantic` | Core | Required for settings validation |
| `pydantic-settings` | Core | Required for environment variable loading |
| `azure-identity` | Optional (`[azure]`) | Only needed for Azure AI embeddings |
| `azure-ai-inference` | Optional (`[azure]`) | Only needed for Azure AI embeddings |

### Why This Split?

Users who bring their own embedder (e.g., OpenAI, Cohere, local models) shouldn't need Azure SDK dependencies. The `[azure]` extra makes this explicit:

```bash
# Minimal installation (bring your own embedder)
pip install agent-framework-neo4j

# With Azure AI embeddings support
pip install agent-framework-neo4j[azure]

# Full development environment
pip install agent-framework-neo4j[all]
```

---

## Version Strategy

Follow semantic versioning aligned with the Agent Framework ecosystem:

| Version Format | Usage |
|----------------|-------|
| `0.1.0` | Initial development |
| `0.1.0b1` | Beta releases |
| `1.0.0` | First stable release |
| `1.0.0b260115` | Date-based beta (matches Agent Framework pattern) |

**Recommendation**: Start with `0.1.0` for initial PyPI release. Move to `1.0.0` when the Agent Framework itself reaches stable release.

---

## Testing Strategy

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures (mock Neo4j, mock embedder)
├── test_provider.py         # Neo4jContextProvider tests
├── test_settings.py         # Settings validation tests
├── test_fulltext.py         # FulltextRetriever tests
├── test_embedder.py         # AzureAIEmbedder tests
└── integration/             # Optional integration tests (require real Neo4j)
    └── test_search.py
```

### Key Test Categories

1. **Unit Tests** (mock all external dependencies)
   - Provider initialization and configuration validation
   - Message filtering and context formatting
   - Settings loading from environment variables

2. **Integration Tests** (optional, require Neo4j instance)
   - End-to-end search operations
   - Graph enrichment queries
   - Connection management

### Mocking Pattern

```python
# conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_neo4j_driver():
    driver = MagicMock()
    driver.verify_connectivity = MagicMock()
    driver.close = MagicMock()
    return driver

@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    embedder.embed_query = MagicMock(return_value=[0.1] * 1536)
    return embedder
```

---

## Documentation Structure

### Library README.md (Top-Level)

```markdown
# agent-framework-neo4j

Neo4j Context Provider for Microsoft Agent Framework - RAG with knowledge graphs.

## Installation

pip install agent-framework-neo4j

# With Azure AI embeddings
pip install agent-framework-neo4j[azure]

## Quick Start

[Minimal working example]

## Features

- Vector, fulltext, and hybrid search modes
- Graph-enriched retrieval with custom Cypher
- Configurable message history windowing
- Pydantic settings for environment-based configuration

## Documentation

- [API Reference](docs/api_reference.md)
- [Architecture](docs/architecture.md)
- [Examples](samples/README.md)

## License

MIT
```

### Samples README.md

```markdown
# Neo4j Context Provider Samples

Demonstration applications for agent-framework-neo4j.

## Prerequisites

- Neo4j database with configured indexes
- Azure AI project (for embeddings)

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env` and configure
3. Install dependencies: `pip install -e ".[samples]"`

## Running Samples

[Interactive menu or direct execution instructions]

## Sample Descriptions

[Table of samples with descriptions]
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --dev
      - run: uv run pytest --cov=agent_framework_neo4j
      - run: uv run mypy src/agent_framework_neo4j
      - run: uv run ruff check src/

  publish:
    needs: test
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          api-token: ${{ secrets.PYPI_API_TOKEN }}
```

---

## Summary

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package name | `agent-framework-neo4j` | Follows Agent Framework ecosystem naming |
| Module name | `agent_framework_neo4j` | PEP 8 compliant, matches package |
| Layout | Flat src layout | Simple, well-supported, recommended by PyPA |
| Build backend | Hatchling | Modern, fast, good src layout support |
| Samples location | Top-level `samples/` | Clear separation, not installed with library |
| Optional deps | `[azure]` extra | Keeps core minimal for users with other embedders |

### Benefits

1. **Clear separation of concerns** - Library code is independent of demo infrastructure
2. **Easy installation** - `pip install agent-framework-neo4j` just works
3. **Discoverable in ecosystem** - Naming aligns with other Agent Framework providers
4. **Flexible dependencies** - Users install only what they need
5. **Professional quality** - Type hints, tests, documentation, CI/CD

### Next Steps

1. Create a new branch for the restructuring work
2. Implement Phase 1 (rename and restructure)
3. Validate all tests pass with new structure
4. Implement Phase 2 (configuration updates)
5. Add documentation and quality tooling (Phase 3)
6. Test PyPI publishing with TestPyPI first
7. Publish to PyPI

---

## References

- [Python Packaging User Guide - src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Writing your pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [pyOpenSci Python Package Guide](https://www.pyopensci.org/python-package-guide/tutorials/pyproject-toml.html)
- [Real Python - Python pyproject.toml Guide](https://realpython.com/python-pyproject-toml/)
- [Microsoft Agent Framework - Context Providers](https://github.com/microsoft/agent-framework)
- [Agent Framework Samples Repository](https://github.com/microsoft/Agent-Framework-Samples)

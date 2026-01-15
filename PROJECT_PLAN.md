# Project Plan: Implement Provider Library Restructure

This plan implements the restructure defined in [PROVIDER_LIBRARY.md](./PROVIDER_LIBRARY.md).

**Important**: This is a complete cut-over. All changes happen atomically. No compatibility layers. No rollback plans. No partial updates.

---

## Phase 1: Create Directory Structure

Create all new directories before moving any files.

### Step 1.1: Create packages directory
- Create `packages/` directory at repository root
- Create `packages/agent-framework-neo4j/` subdirectory
- Create `packages/agent-framework-neo4j/src/` subdirectory
- Create `packages/agent-framework-neo4j/src/agent_framework_neo4j/` subdirectory

### Step 1.2: Create samples directory structure
- Create `samples/` directory at repository root
- Create `samples/basic_fulltext/` subdirectory
- Create `samples/vector_search/` subdirectory
- Create `samples/graph_enriched/` subdirectory
- Create `samples/aircraft_domain/` subdirectory
- Create `samples/shared/` subdirectory

### Step 1.3: Create docs directory
- Create `docs/` directory at repository root

---

## Phase 2: Move Library Files

Move core provider files to the new library package location. Rename files to use underscore prefix for internal modules.

### Step 2.1: Move provider module
- Move `src/neo4j_provider/provider.py` to `packages/agent-framework-neo4j/src/agent_framework_neo4j/_provider.py`

### Step 2.2: Move settings module
- Move `src/neo4j_provider/settings.py` to `packages/agent-framework-neo4j/src/agent_framework_neo4j/_settings.py`

### Step 2.3: Move embedder module
- Move `src/neo4j_provider/embedder.py` to `packages/agent-framework-neo4j/src/agent_framework_neo4j/_embedder.py`

### Step 2.4: Move fulltext module
- Move `src/neo4j_provider/fulltext.py` to `packages/agent-framework-neo4j/src/agent_framework_neo4j/_fulltext.py`

### Step 2.5: Move stop words module
- Move `src/neo4j_provider/stop_words.py` to `packages/agent-framework-neo4j/src/agent_framework_neo4j/_stop_words.py`

### Step 2.6: Create new init file
- Create new `packages/agent-framework-neo4j/src/agent_framework_neo4j/__init__.py` with public API exports
- Export Neo4jContextProvider, Neo4jSettings, AzureAISettings, AzureAIEmbedder, FulltextRetriever
- Add version string

---

## Phase 3: Move Sample Files

Move demo applications to the new samples directory structure.

### Step 3.1: Move basic fulltext sample
- Move `src/samples/context_provider_basic.py` to `samples/basic_fulltext/main.py`
- Move `src/samples/azure_thread_memory.py` to `samples/basic_fulltext/azure_thread_memory.py`

### Step 3.2: Move vector search samples
- Move `src/samples/context_provider_vector.py` to `samples/vector_search/main.py`
- Move `src/samples/semantic_search.py` to `samples/vector_search/semantic_search.py`

### Step 3.3: Move graph enriched sample
- Move `src/samples/context_provider_graph_enriched.py` to `samples/graph_enriched/main.py`

### Step 3.4: Move aircraft domain samples
- Move `src/samples/aircraft_maintenance_search.py` to `samples/aircraft_domain/maintenance_search.py`
- Move `src/samples/aircraft_flight_delays.py` to `samples/aircraft_domain/flight_delays.py`
- Move `src/samples/component_health.py` to `samples/aircraft_domain/component_health.py`

### Step 3.5: Move shared utilities
- Move `src/samples/_utils.py` to `samples/shared/utils.py`
- Move `src/utils/env.py` to `samples/shared/env.py`
- Move `src/utils/logging.py` to `samples/shared/logging.py`
- Move `src/agent.py` to `samples/shared/agent.py`
- Move `src/main.py` to `samples/shared/cli.py`
- Create `samples/shared/__init__.py` with exports

---

## Phase 4: Update Import Statements

Update all import statements in all files to use the new module name.

### Step 4.1: Update library internal imports
- In `_provider.py`: Change `from neo4j_provider.fulltext` to `from ._fulltext`
- In `_provider.py`: Change `from neo4j_provider.settings` to `from ._settings`
- In `_fulltext.py`: Change `from neo4j_provider.stop_words` to `from ._stop_words`

### Step 4.2: Update sample imports
- In all sample files: Change `from neo4j_provider import` to `from agent_framework_neo4j import`
- Update any relative imports to use the new shared module location

### Step 4.3: Update test imports
- In `tests/test_provider.py`: Change `from neo4j_provider import` to `from agent_framework_neo4j import`
- Update any test helper imports

### Step 4.4: Update shared utility imports
- In `samples/shared/agent.py`: Update imports to use new module name
- In `samples/shared/cli.py`: Update imports to reference new sample locations

---

## Phase 5: Create Configuration Files

Create all new pyproject.toml files and update the root configuration.

### Step 5.1: Create root workspace pyproject.toml
- Replace existing `pyproject.toml` with workspace configuration
- Define workspace members: packages/agent-framework-neo4j and samples
- Add workspace source reference for agent-framework-neo4j
- Add tool configurations for pytest, ruff, mypy, coverage
- Remove old package build configuration

### Step 5.2: Create library pyproject.toml
- Create `packages/agent-framework-neo4j/pyproject.toml`
- Set package name to agent-framework-neo4j
- Set version to 0.1.0
- Add description, readme, license, authors
- Add keywords and classifiers
- Define core dependencies: agent-framework-core, neo4j, neo4j-graphrag, pydantic, pydantic-settings
- Define optional azure dependencies: azure-identity, azure-ai-inference
- Define optional dev dependencies: pytest, pytest-asyncio, pytest-cov, mypy, ruff
- Add project URLs
- Configure hatchling build backend

### Step 5.3: Create samples pyproject.toml
- Create `samples/pyproject.toml`
- Set package name to neo4j-provider-samples
- Add dependency on agent-framework-neo4j with azure extra
- Add dependency on agent-framework-azure-ai
- Add dependency on python-dotenv
- Define start-samples script entry point
- Configure hatchling build backend

---

## Phase 6: Create Documentation Files

Create README files for the library and samples.

### Step 6.1: Create library README
- Create `packages/agent-framework-neo4j/README.md`
- Add installation instructions
- Add quick start example
- List features
- Document environment variables

### Step 6.2: Create samples README
- Create `samples/README.md`
- List all available samples with descriptions
- Add setup instructions
- Add instructions for running each sample

### Step 6.3: Create sample-specific README files
- Create `samples/basic_fulltext/README.md` with sample description and usage
- Create `samples/vector_search/README.md` with sample description and usage
- Create `samples/graph_enriched/README.md` with sample description and usage
- Create `samples/aircraft_domain/README.md` with sample description and usage

### Step 6.4: Update root README
- Update `README.md` at repository root
- Describe monorepo structure
- Add quick start commands
- Add publishing instructions

### Step 6.5: Update CLAUDE.md
- Update `CLAUDE.md` with new project structure
- Update command examples to use new paths
- Update module name references

---

## Phase 7: Delete Old Structure

Remove all old files and directories after everything is moved.

### Step 7.1: Delete old src directory
- Delete `src/__init__.py`
- Delete `src/neo4j_provider/` directory and all contents
- Delete `src/samples/` directory and all contents
- Delete `src/utils/` directory and all contents
- Delete `src/agent.py`
- Delete `src/main.py`
- Delete `src/` directory

### Step 7.2: Clean up any remaining old files
- Delete any temporary files created during move
- Delete any backup files if accidentally created
- Delete uv.lock file so it regenerates with new structure

---

## Phase 8: Verification

Verify the new structure works correctly.

### Step 8.1: Sync dependencies
- Run `uv sync --prerelease=allow` to install all workspace packages
- Verify no dependency errors occur

### Step 8.2: Verify imports work
- Run `uv run python -c "from agent_framework_neo4j import Neo4jContextProvider"` to verify library imports
- Run `uv run python -c "from agent_framework_neo4j import Neo4jSettings"` to verify settings import
- Run `uv run python -c "from agent_framework_neo4j import AzureAIEmbedder"` to verify embedder import

### Step 8.3: Run tests
- Run `uv run pytest` to execute test suite
- Verify all tests pass

### Step 8.4: Run linting
- Run `uv run ruff check packages/agent-framework-neo4j/src` to check for linting errors
- Run `uv run ruff check samples/` to check samples for linting errors

### Step 8.5: Run type checking
- Run `uv run mypy packages/agent-framework-neo4j/src/agent_framework_neo4j` to check types
- Fix any type errors that appear

### Step 8.6: Test samples
- Run one sample from each category to verify they work
- Run `uv run python samples/basic_fulltext/main.py` (may need Neo4j connection)
- Verify no import errors occur

### Step 8.7: Test build
- Run `uv build --package agent-framework-neo4j` to build the library
- Verify wheel and sdist files are created
- Check that only library files are included in the package

---

## Phase 9: Final Cleanup

Final cleanup and preparation for use.

### Step 9.1: Regenerate lock file
- Delete `uv.lock` if not already done
- Run `uv sync --prerelease=allow` to regenerate lock file with new structure

### Step 9.2: Update gitignore if needed
- Verify `.gitignore` includes appropriate entries for new structure
- Add any new patterns if needed

### Step 9.3: Create LICENSE file if missing
- Verify LICENSE file exists at repository root
- Create MIT LICENSE file if not present

### Step 9.4: Create docs placeholder files
- Create `docs/getting_started.md` with placeholder content
- Create `docs/api_reference.md` with placeholder content
- Create `docs/architecture.md` with placeholder content

---

## Checklist

Use this checklist to track completion:

### Phase 1: Create Directory Structure
- [x] Create packages/agent-framework-neo4j/src/agent_framework_neo4j/
- [x] Create samples/basic_fulltext/
- [x] Create samples/vector_search/
- [x] Create samples/graph_enriched/
- [x] Create samples/aircraft_domain/
- [x] Create samples/shared/
- [x] Create docs/

### Phase 2: Move Library Files
- [x] Move provider.py to _provider.py
- [x] Move settings.py to _settings.py
- [x] Move embedder.py to _embedder.py
- [x] Move fulltext.py to _fulltext.py
- [x] Move stop_words.py to _stop_words.py
- [x] Create new __init__.py with exports

### Phase 3: Move Sample Files
- [x] Move basic fulltext samples
- [x] Move vector search samples
- [x] Move graph enriched sample
- [x] Move aircraft domain samples
- [x] Move shared utilities
- [x] Create shared __init__.py

### Phase 4: Update Import Statements
- [x] Update library internal imports
- [x] Update sample imports
- [x] Update test imports
- [x] Update shared utility imports

### Phase 5: Create Configuration Files
- [x] Create root workspace pyproject.toml
- [x] Create library pyproject.toml
- [x] Create samples pyproject.toml

### Phase 6: Create Documentation Files
- [x] Create library README
- [x] Create samples README
- [x] Create sample-specific READMEs
- [x] Update root README
- [x] Update CLAUDE.md

### Phase 7: Delete Old Structure
- [x] Delete src/ directory entirely

### Phase 8: Verification
- [x] Sync dependencies successfully
- [x] Verify library imports work
- [x] Run tests successfully
- [x] Run linting successfully
- [x] Run type checking successfully
- [x] Test at least one sample
- [x] Test build successfully

### Phase 9: Final Cleanup
- [x] Regenerate lock file
- [x] Verify gitignore
- [x] Verify LICENSE exists
- [x] Create docs placeholders

---

## Summary

| Phase | Description | Steps |
|-------|-------------|-------|
| 1 | Create Directory Structure | 3 steps |
| 2 | Move Library Files | 6 steps |
| 3 | Move Sample Files | 5 steps |
| 4 | Update Import Statements | 4 steps |
| 5 | Create Configuration Files | 3 steps |
| 6 | Create Documentation Files | 5 steps |
| 7 | Delete Old Structure | 2 steps |
| 8 | Verification | 7 steps |
| 9 | Final Cleanup | 4 steps |

**Total**: 9 phases, 39 steps

---

## Reference

See [PROVIDER_LIBRARY.md](./PROVIDER_LIBRARY.md) for:
- Complete file mapping table
- Full pyproject.toml configurations
- Import change mappings
- Module structure details

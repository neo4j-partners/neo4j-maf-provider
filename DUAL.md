# Dual Language Support Proposal

This document proposes updating the Neo4j MAF Provider repository to support both Python and .NET implementations, following the same organizational pattern used by the Microsoft Agent Framework.

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | Complete | Created python/ directory, moved all Python code |
| **Phase 2** | Complete | Reorganized documentation |
| **Phase 3** | Complete | Updated root configuration files |
| **Phase 4** | Pending | CI/CD and scripts updates |
| **Phase 5** | Pending | .NET placeholder structure |

---

## Current State

The repository is currently Python-only with the following structure:

- Root-level UV workspace configuration
- `packages/agent-framework-neo4j/` - Publishable Python library
- `samples/` - Python demo applications
- `tests/` - Python tests
- `docs/` - Documentation
- Root documentation files (README.md, CLAUDE.md)

## Target State

A dual-language monorepo with clean separation between Python and .NET:

```
neo4j-maf-provider/
├── python/                    # All Python code and config
│   ├── packages/
│   ├── samples/
│   ├── tests/
│   ├── pyproject.toml
│   ├── uv.lock
│   └── README.md
├── dotnet/                    # Future .NET implementation
│   ├── src/
│   ├── samples/
│   ├── tests/
│   └── README.md
├── docs/                      # Shared documentation
├── README.md                  # Root readme pointing to both languages
├── CLAUDE.md                  # Updated AI assistant guidelines
├── CONTRIBUTING.md            # Shared contribution guidelines
└── LICENSE
```

## Design Principles

Following the agent-framework pattern:

1. **Clean Language Separation** - Python and .NET are completely independent build systems with no cross-language dependencies

2. **Language-Native Tooling** - Python continues using UV workspace and pyproject.toml; .NET will use MSBuild with Directory.Build.props

3. **Independent Package Ecosystems** - Python publishes to PyPI; .NET will publish to NuGet

4. **Shared Documentation** - Architecture docs, design decisions, and governance docs remain at root level

5. **Mirror Feature Parity** - Both implementations provide the same capabilities (context provider, settings, embedder)

## Key Decisions

### Keep Samples Flat

The samples directory structure remains unchanged when moved to `python/samples/`. No reorganization of the sample applications themselves. The existing organization (basic_fulltext, vector_search, graph_enriched, aircraft_domain, memory_basic) is preserved exactly as-is.

### Documentation Split

- **Root-level docs**: README (overview), CLAUDE.md, CONTRIBUTING, LICENSE, governance docs
- **Shared docs folder**: Architecture, design decisions, API concepts
- **Language-specific docs**: Installation guides, language-specific API reference, quickstart

### Environment and Azure Configuration

The Azure infrastructure (`samples/azure.yaml`, `samples/infra/`) remains in the Python samples for now. When .NET is added, samples may share infrastructure or have separate deployments.

---

## Implementation Plan

### Phase 1: Create Python Directory Structure

**Goal**: Move all Python code into a `python/` directory without breaking functionality.

**Steps**:

1. Create the `python/` directory at repository root

2. Move the following into `python/`:
   - `packages/` directory (entire contents)
   - `samples/` directory (entire contents, no reorganization)
   - `tests/` directory (entire contents)
   - `pyproject.toml` (root workspace config)
   - `uv.lock` (dependency lock file)
   - `.python-version` (if exists)

3. Move Python-specific cache/config directories:
   - `.mypy_cache/`
   - `.ruff_cache/`
   - `.pytest_cache/`
   - `.venv/` (will be recreated)

4. Update `python/pyproject.toml` workspace member paths (they should still be relative, just confirming they work from new location)

5. Delete and recreate virtual environment:
   - Remove old `.venv/`
   - Run `uv sync --prerelease=allow` from `python/` directory

6. Verify all commands work from `python/` directory:
   - `uv run pytest`
   - `uv run start-samples`
   - `uv run mypy packages/agent-framework-neo4j/agent_framework_neo4j`
   - `uv run ruff check packages/agent-framework-neo4j/agent_framework_neo4j`
   - `uv build --package agent-framework-neo4j`

### Phase 2: Reorganize Documentation

**Goal**: Split documentation between root (shared) and language-specific locations.

**Steps**:

1. Keep at repository root:
   - `README.md` (update to be a landing page pointing to both languages)
   - `CLAUDE.md` (update paths and add dual-language guidance)
   - `LICENSE`
   - `CONTRIBUTING.md` (create if not exists, or keep existing)

2. Move to `docs/` (shared documentation):
   - `docs/architecture.md` (keep)
   - `docs/api_reference.md` (move to python-specific, create shared concepts doc)
   - Create `docs/design/` for architecture decisions
   - Move `temp/NEO4J_PROVIDER_ARCHITECTURE.md` to `docs/architecture/` (clean up temp)

3. Create `python/` documentation:
   - `python/README.md` - Python quickstart and installation
   - `python/DEV_SETUP.md` - Python development environment setup
   - `python/docs/` - Python-specific documentation
   - Move `docs/PUBLISH.md` to `python/docs/PUBLISH.md`

4. Update all internal documentation links to reflect new paths

5. Update `python/samples/` README files if they reference root paths

### Phase 3: Update Root Configuration

**Goal**: Create root-level configuration appropriate for a dual-language repository.

**Steps**:

1. Create new root `README.md`:
   - Project overview and description
   - Link to Python quickstart (`python/README.md`)
   - Link to .NET quickstart (placeholder for future)
   - Link to shared documentation
   - Badges for both package ecosystems (PyPI, future NuGet)

2. Update `CLAUDE.md`:
   - Update all file paths to include `python/` prefix
   - Add section noting dual-language structure
   - Add placeholder guidance for future .NET work
   - Update commands section with `cd python` prefix

3. Create `CONTRIBUTING.md`:
   - General contribution guidelines
   - Point to language-specific setup guides
   - Code of conduct reference

4. Update `.gitignore`:
   - Ensure patterns work for both `python/` and future `dotnet/` directories
   - Add .NET-specific ignore patterns in preparation

5. Remove or archive obsolete root files:
   - Move `MEM_EXAMPLE.md` to `python/docs/` or `docs/examples/`
   - Clean up `temp/` directory contents

### Phase 4: Update CI/CD and Scripts

**Goal**: Ensure automation works with new directory structure.

**Steps**:

1. Update any GitHub workflows (if present in `.github/`):
   - Update working directory to `python/`
   - Update paths for Python checks

2. Update `scripts/version-bump.sh`:
   - Update paths to include `python/` prefix

3. Update devcontainer configuration:
   - Update `.devcontainer/` to set working directory appropriately
   - Consider creating `python/` and `dotnet/` specific devcontainers

4. Verify Azure deployment still works:
   - `cd python/samples && azd up` should function correctly
   - Update any hardcoded paths in bicep or scripts

### Phase 5: Prepare for .NET (Future)

**Goal**: Create placeholder structure for .NET implementation.

**Steps**:

1. Create `dotnet/` directory structure:
   - `dotnet/README.md` - Placeholder with "Coming Soon" message
   - `dotnet/src/` - Empty, ready for implementation
   - `dotnet/samples/` - Empty, ready for samples
   - `dotnet/tests/` - Empty, ready for tests

2. Create initial .NET configuration files (placeholders):
   - `dotnet/Directory.Build.props` - Basic MSBuild properties
   - `dotnet/Directory.Packages.props` - Dependency version management template
   - `dotnet/neo4j-provider.sln` - Solution file placeholder

3. Document planned .NET implementation in `dotnet/README.md`:
   - Target namespace: `Microsoft.Agents.AI.Neo4j` or similar
   - Planned packages and their purposes
   - Reference to Python implementation for feature parity

---

## Migration Checklist

### Before Starting

- [ ] Ensure all tests pass in current structure
- [ ] Commit any pending changes
- [ ] Create a migration branch

### Phase 1 Verification

- [ ] `python/` directory exists with all code
- [ ] `uv sync --prerelease=allow` succeeds
- [ ] `uv run pytest` passes
- [ ] `uv run start-samples` runs
- [ ] `uv build --package agent-framework-neo4j` succeeds

### Phase 2 Verification

- [ ] Root README points to both languages
- [ ] CLAUDE.md has updated paths
- [ ] No broken documentation links
- [ ] `docs/` contains shared documentation

### Phase 3 Verification

- [ ] Root configuration files updated
- [ ] .gitignore covers both languages
- [ ] No obsolete files at root

### Phase 4 Verification

- [ ] CI/CD workflows updated (if applicable)
- [ ] Scripts work with new paths
- [ ] Azure deployment functions correctly

### Phase 5 Verification

- [ ] `dotnet/` placeholder structure exists
- [ ] dotnet/README.md explains future plans

---

## Risks and Mitigations

### Risk: Breaking Existing Users

If anyone has cloned the repository and expects the current structure, their workflows will break.

**Mitigation**: This is an internal/workshop project. Document the change clearly in release notes and update any external references.

### Risk: Path References in Code

Hardcoded paths in configuration or code may break.

**Mitigation**: Search for absolute paths and update them. Most paths should be relative and continue to work.

### Risk: Azure Deployment Paths

The Azure configuration may have assumptions about directory structure.

**Mitigation**: Test `azd up` thoroughly after migration. The azure.yaml and bicep files should be path-agnostic.

---

## Success Criteria

1. All Python functionality works from `python/` directory
2. Documentation is properly split between shared and language-specific
3. Root directory serves as a clean landing page for the dual-language project
4. Structure mirrors the Microsoft Agent Framework pattern
5. Ready to add .NET implementation without further reorganization

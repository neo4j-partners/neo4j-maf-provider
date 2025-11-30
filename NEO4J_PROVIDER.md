# Neo4j Context Provider Proposal

A step-by-step plan to create a Neo4j context provider for the Microsoft Agent Framework, focusing on RAG enhancement, multi-hop reasoning, path-based retrieval, and contextual relevance.

---

## Goals

Build a Neo4j context provider that enhances agent responses by:

1. **RAG Enhancement** - Retrieve relevant knowledge graph data to augment LLM context
2. **Multi-hop Reasoning** - Traverse multiple relationship levels to find connected information
3. **Path-based Retrieval** - Return paths between entities, not just nodes
4. **Contextual Relevance** - Filter and rank retrieved data based on the user's query

---

## Design Principles

- **Incremental Complexity** - Start with the absolute minimum and add features one at a time
- **Test at Every Phase** - Each phase includes validation before moving forward
- **Learn from Existing Providers** - Follow patterns established by Azure AI Search, Mem0, and Redis providers
- **Reuse Existing Code** - Leverage the existing `Neo4jClient` and `VectorSearchClient` in this project
- **Keep It Simple** - This is a demo/learning project, not production-ready

---

## Existing Code to Reuse

This project already has Neo4j infrastructure that the provider will use via composition:

### From `src/neo4j_client.py`

| Component | Purpose | How Provider Uses It |
|-----------|---------|---------------------|
| `Neo4jConfig` | Pydantic settings for NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD | Provider accepts config or creates from environment |
| `Neo4jClient` | Async context manager with connection lifecycle | Provider wraps/composes with this client |
| `Neo4jClient.execute_query()` | Run arbitrary Cypher queries | Used for all graph queries |
| `Neo4jClient.get_entity_relationships()` | Single-hop relationship retrieval | Reused directly for Phase 2 |
| `Neo4jClient.get_schema()` | Retrieve graph schema | Optional: for validation |
| `ALLOWED_ENTITY_LABELS` | Valid entity types for the domain | Used for entity type validation |
| `GraphSchema` | Schema representation | Optional: expose to agent |

### From `src/vector_search.py` (Optional Enhancement)

| Component | Purpose | How Provider Uses It |
|-----------|---------|---------------------|
| `VectorSearchClient` | Semantic search with graph context | Optional: combine with graph traversal |
| `VectorSearchConfig` | Embedding configuration | Pass through if using vector search |

---

## Reference Architecture

The provider will follow the standard context provider lifecycle:

1. `__aenter__` - Enter the wrapped `Neo4jClient` context (connection already managed)
2. `thread_created` - Optionally track conversation threads in the graph
3. `invoking` - Query Neo4j based on user message, return relevant context
4. `invoked` - Optionally store conversation entities in the graph
5. `__aexit__` - Exit the wrapped `Neo4jClient` context

**Key Design Decision**: Use composition with `Neo4jClient`, not inheritance. The provider accepts a `Neo4jClient` instance and delegates all database operations to it.

---

## Key References

### Existing Project Code

| File | Purpose |
|------|---------|
| `src/neo4j_client.py` | Neo4j configuration, connection, and query methods to reuse |
| `src/vector_search.py` | Optional vector search integration |
| `src/agent.py` | Existing agent setup patterns |

### Framework Source Code

| File | Purpose |
|------|---------|
| `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/agent_framework/_memory.py` | Base `Context` and `ContextProvider` classes |
| `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/context_providers/simple_context_provider.py` | Simple provider example showing basic patterns |
| `/Users/ryanknight/projects/azure/agent-framework/python/packages/azure-ai-search/agent_framework_azure_ai_search/_search_provider.py` | Full-featured RAG provider example |
| `/Users/ryanknight/projects/azure/agent-framework/python/packages/mem0/agent_framework_mem0/_provider.py` | Memory provider with scoping patterns |
| `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/tests/core/test_memory.py` | Testing patterns for context providers |

### Documentation

| File | Purpose |
|------|---------|
| `/Users/ryanknight/projects/workshops/neo4j-maf-provider/CONTEXT_PROVIDERS.md` | Context provider architecture overview |
| `/Users/ryanknight/projects/azure/agent-framework/CONTEXT_PROVIDERS.md` | Official framework documentation |

---

## Implementation Summary

| Phase | Goal | Reused Code |
|-------|------|-------------|
| 0 | Static provider (no Neo4j) | None - validates interface |
| 1 | Neo4jClient composition | `Neo4jClient`, `Neo4jConfig` |
| 2 | Single-hop relationships | `Neo4jClient.get_entity_relationships()` |
| 3 | Multi-hop traversal | `Neo4jClient.execute_query()` |
| 4 | Path between two entities | `Neo4jClient.execute_query()` + `shortestPath` |
| 5 | Filtering and limits | Pure Python logic |
| 6 | Vector search (optional) | `VectorSearchClient.search()` |

---

## Implementation Plan

### Phase 0: Static Context Provider (No Neo4j)

**Goal**: Create the simplest possible provider that returns hardcoded context. This validates we understand the provider interface before adding any complexity.

**What It Does**:
- Returns a fixed string of instructions in the `invoking` method
- Does nothing in other lifecycle methods
- Verifies the provider integrates correctly with ChatAgent

**Why Start Here**:
- Eliminates external dependencies (no database needed)
- Confirms understanding of the Context and ContextProvider interfaces
- Creates a foundation to build upon

**Testing Plan**:
- Create provider instance and call `invoking` directly
- Verify it returns a `Context` object with expected instructions
- Integrate with a ChatAgent and confirm the static instructions appear in agent responses
- Use print statements or logging to verify lifecycle methods are called in the correct order

**Todo List**:
1. Create `src/neo4j_context_provider.py`
2. Import `ContextProvider` and `Context` from `agent_framework`
3. Create `Neo4jContextProvider` class extending `ContextProvider`
4. Implement `invoking` method to return static instructions string
5. Write a simple test script in `tests/` that creates the provider and calls `invoking`
6. Verify the test passes and Context is returned correctly
7. Code review and testing

---

### Phase 1: Neo4jClient Composition

**Goal**: Integrate with the existing `Neo4jClient` from `src/neo4j_client.py` using composition pattern.

**What It Does**:
- Accepts a `Neo4jClient` instance in the constructor
- Delegates connection lifecycle to the wrapped client
- Manages the client context in `__aenter__` and `__aexit__`
- Still returns static context (no queries yet)

**Why This Phase**:
- Reuses existing connection management from `neo4j_client.py`
- No need to reimplement driver creation, error handling, or cleanup
- Follows composition pattern used by other framework providers

**Reused Code**:
- `Neo4jClient` handles all connection logic
- `Neo4jConfig` provides environment-based configuration
- Error handling already implemented (AuthError, ServiceUnavailable)

**Testing Plan**:
- Test that provider enters and exits client context correctly
- Verify client is connected after provider `__aenter__`
- Verify cleanup happens even if exception occurs
- Test with missing Neo4j (should get helpful error from Neo4jClient)

**Todo List**:
1. Add constructor parameter for `Neo4jClient` instance
2. Store client reference as instance variable
3. Implement `__aenter__` to enter the client context
4. Implement `__aexit__` to exit the client context
5. Update test to use real `Neo4jClient` with `Neo4jConfig`
6. Test with Docker Neo4j instance to verify connection works
7. Code review and testing

---

### Phase 2: Single-Hop Relationship Retrieval

**Goal**: Use the existing `get_entity_relationships()` method to find relationships for entities mentioned in the query.

**What It Does**:
- Extracts entity names from the user's message (simple keyword extraction)
- Calls `Neo4jClient.get_entity_relationships()` for each potential entity
- Formats the relationship results as context instructions
- Returns context that helps the agent answer relationship questions

**Reused Code**:
- `Neo4jClient.get_entity_relationships()` - already implements single-hop traversal
- The method already filters out Document/Chunk nodes
- The method already includes source_type, relationship, target_type

**Context Format** (from existing method output):
- "[Source] ([SourceType]) --[RELATIONSHIP]--> [Target] ([TargetType])"

**Testing Plan**:
- Use existing graph data or seed test data with known relationships
- Send message mentioning an entity name (e.g., "Tell me about Apple")
- Verify relationships for that entity appear in the returned context
- Test with entity that has no relationships - verify empty context gracefully
- Test with multiple potential entity names in one message

**Todo List**:
1. Implement simple entity extraction (split message into words, filter stopwords)
2. In `invoking`, call `get_entity_relationships()` for extracted terms
3. Format relationship results as readable context string
4. Handle case where no relationships found (return empty Context)
5. Add limit parameter to control max relationships returned
6. Write test with seeded Neo4j data
7. Code review and testing

---

### Phase 3: Custom Cypher for Multi-Hop Traversal

**Goal**: Extend beyond single-hop by writing custom Cypher queries using `execute_query()`.

**What It Does**:
- Uses `Neo4jClient.execute_query()` for flexible Cypher execution
- Implements 2-hop traversal to find indirect relationships
- Returns paths showing how entities connect through intermediaries

**Why Custom Cypher**:
- `get_entity_relationships()` only does single-hop
- Multi-hop requires variable-length path patterns
- `execute_query()` allows any valid Cypher

**Context Format**:
- "[Entity A] --[REL1]--> [Intermediate] --[REL2]--> [Entity B]"
- Shows the reasoning chain

**Testing Plan**:
- Create graph with 2-hop paths (A->B->C)
- Query for entity A and verify path to C is found
- Test with configurable hop limit (1, 2, or 3)
- Verify performance is acceptable (queries should complete in <1 second)

**Todo List**:
1. Write Cypher query with variable-length path pattern `[*1..2]`
2. Add constructor parameter for max_hops (default: 2)
3. Call `execute_query()` with the multi-hop Cypher
4. Extract path nodes and relationships from results
5. Format paths as readable context strings
6. Write tests for 2-hop and 3-hop scenarios
7. Code review and testing

---

### Phase 4: Path-Based Retrieval Between Two Entities

**Goal**: Find and return explicit paths between two entities mentioned in the query.

**What It Does**:
- Detects when user mentions two potential entities
- Uses Cypher `shortestPath` to find connection between them
- Falls back to single-entity multi-hop search if only one entity found
- Uses `execute_query()` for the path-finding Cypher

**Use Case**:
- "How is Apple connected to Tim Cook?"
- "What's the relationship between Product X and Company Y?"

**Context Format**:
- "Connection between [Entity A] and [Entity B]:"
- "  [A] --[REL1]--> [Intermediate] --[REL2]--> [B]"

**Testing Plan**:
- Create graph with known paths between specific entities
- Query with both entities mentioned
- Verify the path is found and formatted correctly
- Test with unconnected entities - verify appropriate message
- Test with single entity - verify fallback to Phase 3 behavior

**Todo List**:
1. Enhance entity extraction to identify multiple potential entities
2. Write Cypher using `shortestPath()` function
3. Call `execute_query()` with path-finding query
4. Format path result showing full connection chain
5. Implement fallback to multi-hop when only one entity found
6. Handle case where no path exists between entities
7. Write tests for path finding scenarios
8. Code review and testing

---

### Phase 5: Contextual Relevance Filtering

**Goal**: Improve the quality of returned context by filtering and limiting results.

**What It Does**:
- Limits context size to avoid overwhelming the LLM
- Removes duplicate relationships from results
- Truncates very long property values
- Prioritizes direct matches over indirect ones

**Why This Matters**:
- LLMs have context limits
- Duplicate information wastes tokens
- Focused context leads to better responses

**Configuration Options**:
- Maximum context length in characters (default: 2000)
- Property value truncation length (default: 200)
- Maximum results per query (default: 10)

**Testing Plan**:
- Create graph with many potential results
- Verify results are limited to configured maximum
- Verify duplicates are removed
- Test with very long property values - verify truncation

**Todo List**:
1. Add constructor parameters for limits (max_context_chars, max_results)
2. Implement deduplication by relationship signature
3. Implement context length check before returning
4. Implement property value truncation for long strings
5. Write tests for each filtering feature
6. Code review and testing

---

### Phase 6 (Optional): Vector Search Integration

**Goal**: Combine graph traversal with semantic search using existing `VectorSearchClient`.

**What It Does**:
- Uses `VectorSearchClient` to find semantically similar chunks
- Enriches vector results with graph context from related entities
- Provides both semantic relevance and relationship context

**Reused Code**:
- `VectorSearchClient.search()` - semantic search with graph context
- Already returns company and risk metadata from graph traversal

**Why Optional**:
- Requires Azure AI Foundry embeddings configuration
- May not be needed for all use cases
- Can be added as an enhancement after core phases work

**Testing Plan**:
- Configure `VectorSearchConfig` with embeddings endpoint
- Test that vector results include graph context
- Verify combined results are properly formatted

**Todo List**:
1. Add optional `VectorSearchClient` parameter to constructor
2. When provided, call `search()` in `invoking` alongside graph queries
3. Combine vector results with graph traversal results
4. Format combined results appropriately
5. Write tests with mock vector search
6. Code review and testing

---

## Testing Strategy

### Unit Testing

Follow the pattern from `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/tests/core/test_memory.py`:

- Create a `MockNeo4jDriver` for unit tests that don't need real database
- Test each lifecycle method in isolation
- Verify correct Context objects are returned
- Test error handling for each phase

### Integration Testing

- Use a local Neo4j instance (Docker recommended)
- Seed with known test data before each test
- Clean up test data after tests complete
- Test full lifecycle with ChatAgent

### Manual Validation

At each phase, manually run the provider with a ChatAgent and verify:
- The agent's responses incorporate the graph context appropriately
- The context appears in the expected format
- No errors or warnings in logs

---

## File Structure

Provider fits into the existing project structure:

```
neo4j-maf-provider/
├── src/
│   ├── neo4j_client.py          # EXISTING - reuse this
│   ├── vector_search.py         # EXISTING - optional reuse
│   ├── neo4j_context_provider.py  # NEW - the provider implementation
│   ├── agent.py                 # EXISTING - agent configuration
│   └── ...
├── tests/
│   ├── test_neo4j_context_provider.py  # NEW - provider tests
│   └── ...
├── pyproject.toml
├── CLAUDE.md
├── CONTEXT_PROVIDERS.md
└── NEO4J_PROVIDER.md
```

**Key Point**: The provider is a single file in `src/`, not a separate package. It imports from existing modules like `neo4j_client`.

---

## Dependencies

All required packages are already in the project:

| Package | Status | Purpose |
|---------|--------|---------|
| `agent-framework` | Already installed | Base `ContextProvider` and `Context` classes |
| `neo4j` | Already installed | Async driver (used by `neo4j_client.py`) |
| `pydantic` | Already installed | Configuration (used by `Neo4jConfig`) |
| `pydantic-settings` | Already installed | Environment-based settings |
| `pytest` | Already installed | Testing |
| `pytest-asyncio` | May need to add | Async test support |

No new dependencies required for core functionality.

---

## Out of Scope for This Demo

The following are explicitly not included to keep this project simple:

- Automatic entity extraction using LLM (would add complexity and cost; using simple keyword extraction instead)
- Graph schema migrations or setup (assume graph already populated)
- Production error handling and retry logic
- Caching of query results
- Connection pooling configuration (using Neo4jClient defaults)
- Writing to the graph in `invoked` method (read-only for simplicity)
- Complex NLP for entity recognition (using simple string matching)

**Note**: Vector search IS available via Phase 6 using existing `VectorSearchClient`, but is optional.

---

## Success Criteria

Each phase is complete when:

1. All todo items are checked off
2. Unit tests pass
3. Integration tests pass with real Neo4j
4. Manual testing with ChatAgent shows expected behavior
5. Code has been reviewed for:
   - Following framework patterns from reference files
   - Proper async/await usage
   - Clear error messages
   - Reasonable defaults

---

## Implementation Status

### Phase 0: Static Context Provider ✅ COMPLETE

**Date**: 2025-11-29

**Files Created**:
- `src/neo4j_context_provider.py` - Provider implementation
- `tests/test_neo4j_context_provider.py` - Test suite
- `tests/__init__.py` - Test package

**Test Results**: 4/4 tests passing
```
tests/test_neo4j_context_provider.py::TestPhase0StaticProvider::test_invoking_returns_context PASSED
tests/test_neo4j_context_provider.py::TestPhase0StaticProvider::test_invoking_returns_instructions PASSED
tests/test_neo4j_context_provider.py::TestPhase0StaticProvider::test_invoking_with_single_message PASSED
tests/test_neo4j_context_provider.py::TestPhase0StaticProvider::test_context_manager_protocol PASSED
```

**Validation**:
- Provider extends `ContextProvider` correctly
- `invoking()` returns `Context` object with instructions
- Works as async context manager
- Handles both single message and message list

---

### Phase 1: Neo4jClient Composition ✅ COMPLETE

**Date**: 2025-11-29

**Changes to `src/neo4j_context_provider.py`**:
- Added `neo4j_client` parameter to constructor (optional, for backward compatibility)
- Implemented `__aenter__` to enter client context
- Implemented `__aexit__` to exit client context with proper cleanup
- Added `is_connected` property to check connection state
- Provider manages client lifecycle (enters/exits client context)

**Key Design Decisions**:
- Client is optional - provider works without Neo4j (returns static context)
- Uses composition, not inheritance - delegates to `Neo4jClient`
- Tracks `_owns_client_context` to ensure cleanup happens only once

**Test Results**: 8/8 tests passing (4 Phase 0 + 4 Phase 1)
```
tests/test_neo4j_context_provider.py::TestPhase1Neo4jClientComposition::test_provider_without_client PASSED
tests/test_neo4j_context_provider.py::TestPhase1Neo4jClientComposition::test_provider_with_mock_client PASSED
tests/test_neo4j_context_provider.py::TestPhase1Neo4jClientComposition::test_client_context_cleanup_on_exception PASSED
tests/test_neo4j_context_provider.py::TestPhase1Neo4jClientComposition::test_is_connected_property PASSED
```

**Validation**:
- Provider enters/exits Neo4jClient context correctly
- Cleanup happens even if exception occurs
- Works with or without a client provided
- `is_connected` property reflects actual state

---

### Phase 2: Single-Hop Relationship Retrieval ✅ COMPLETE

**Date**: 2025-11-29

**Changes to `src/neo4j_context_provider.py`**:
- Added `STOPWORDS` constant for entity extraction filtering
- Added `max_relationships` constructor parameter (default: 10)
- Implemented `_extract_query_text()` - extracts text from messages
- Implemented `_extract_potential_entities()` - simple keyword extraction with stopword filtering
- Implemented `_format_relationships()` - formats relationship data as context instructions
- Updated `invoking()` to query Neo4j for relationships when connected

**Key Design Decisions**:
- Simple keyword extraction (no LLM needed) - filters stopwords, keeps meaningful words
- Uses existing `Neo4jClient.get_entity_relationships()` method
- Deduplicates relationships by source|relationship|target key
- Enforces max_relationships limit
- Returns empty Context if no relationships found (not static context)
- Gracefully handles query errors (logs warning, continues)

**Reused Code**:
- `Neo4jClient.get_entity_relationships()` - single-hop traversal already implemented
- Filters Document/Chunk nodes automatically
- Returns source_type, relationship, target_type

**Test Results**: 24/24 tests passing
```
TestPhase2EntityExtraction (7 tests):
- test_extract_potential_entities_basic PASSED
- test_extract_potential_entities_multiple PASSED
- test_extract_potential_entities_deduplication PASSED
- test_extract_potential_entities_empty PASSED
- test_extract_potential_entities_only_stopwords PASSED
- test_extract_query_text_single_message PASSED
- test_extract_query_text_multiple_messages PASSED

TestPhase2RelationshipFormatting (4 tests):
- test_format_relationships_basic PASSED
- test_format_relationships_multiple PASSED
- test_format_relationships_empty PASSED
- test_format_relationships_missing_type PASSED

TestPhase2RelationshipRetrieval (5 tests):
- test_invoking_with_relationships PASSED
- test_invoking_no_relationships_found PASSED
- test_invoking_deduplicates_relationships PASSED
- test_invoking_respects_max_relationships PASSED
- test_invoking_handles_query_error PASSED
```

**Validation**:
- Entity extraction filters stopwords correctly
- Relationships are formatted with source/target types
- Deduplication prevents duplicate relationships
- max_relationships limit is enforced
- Errors are handled gracefully

**Context Output Format**:
```
## Knowledge Graph Context

The following relationships were found in the knowledge graph:

- Apple (Company) --[MAKES]--> iPhone (Product)
- Apple (Company) --[FOUNDED_BY]--> Steve Jobs (Executive)
```

---

### Demo Scripts ✅ ADDED

**Date**: 2025-11-29

**Files Added**:
- `src/discover_schema.py` - Neo4j schema discovery script
- `src/start_agent.py` - Updated to demonstrate context provider

**Running the Demo**:
```bash
# Discover Neo4j schema and find example entities
uv run python src/discover_schema.py

# Run the context provider demo (non-interactive)
uv run start-agent
```

**Demo Output** (example for Apple query):
```
[Context Provider Processing]

  Extracted entities: ['APPLE', 'INC', 'products']
  Relationships found for 'APPLE':
    - APPLE INC --[MENTIONS]--> Tim Cook
    - APPLE INC --[MENTIONS]--> iPhone
    - APPLE INC --[MENTIONS]--> Mac
    ... and 2 more

[Agent Response]

  Apple Inc. is a prominent technology company that produces a range
  of innovative products. Some of their key products include:
  - iPhone: Apple's flagship smartphone...
  - Mac: A line of personal computers...
```

---

### Phase 3: Custom Cypher for Multi-Hop Traversal ✅ COMPLETE

**Date**: 2025-11-29

**Changes to `src/neo4j_context_provider.py`**:
- Added `max_hops` constructor parameter (default: 1, valid: 1-5)
- Added `_get_multi_hop_paths()` method using `execute_query()` with variable-length path patterns
- Added `_format_paths()` method for formatting multi-hop paths as context
- Refactored `invoking()` to branch based on `max_hops` setting
- Added `_invoking_single_hop()` for single-hop retrieval (max_hops=1)
- Added `_invoking_multi_hop()` for multi-hop traversal (max_hops>1)

**Key Design Decisions**:
- Backward compatible: `max_hops=1` (default) uses existing single-hop behavior
- Multi-hop enabled with `max_hops=2` or higher
- Maximum of 5 hops to prevent expensive queries
- Uses `execute_query()` with validated integer in f-string (safe since validated in constructor)
- Path deduplication by node names + relationship types signature
- Modular code: separate methods for single-hop and multi-hop logic

**Reused Code**:
- `Neo4jClient.execute_query()` - flexible Cypher execution
- Same entity extraction and context structure as single-hop
- Consistent formatting style between relationships and paths

**Test Files Created**:
- `tests/test_multi_hop_traversal.py` - 17 new tests for multi-hop functionality

**Test Results**: 41/41 tests passing
```
tests/test_multi_hop_traversal.py:
  TestMaxHopsConfiguration (4 tests): all PASSED
  TestPathFormatting (6 tests): all PASSED
  TestMultiHopRetrieval (7 tests): all PASSED

tests/test_neo4j_context_provider.py:
  TestStaticContextProvider (4 tests): all PASSED
  TestClientLifecycle (4 tests): all PASSED
  TestEntityExtraction (7 tests): all PASSED
  TestRelationshipFormatting (4 tests): all PASSED
  TestSingleHopRetrieval (5 tests): all PASSED
```

**Validation**:
- max_hops parameter validates range (1-5) in constructor
- Multi-hop uses variable-length paths `[*1..N]` in Cypher
- Path formatting shows full reasoning chain with intermediates
- Deduplication prevents duplicate paths in results
- max_relationships limit respected for paths
- Errors handled gracefully (logged, returns empty context)
- Cypher query includes correct max_hops value

**Multi-Hop Context Output Format**:
```
## Knowledge Graph Context

The following paths were found in the knowledge graph:

- Apple (Company) --[LED_BY]--> Tim Cook (Executive) --[GRADUATED_FROM]--> Stanford (University)
- Apple (Company) --[MAKES]--> iPhone (Product) --[USED_IN]--> Mobile Market (Industry)
```

**Next**: Phase 4 - Path-Based Retrieval Between Two Entities (future work)

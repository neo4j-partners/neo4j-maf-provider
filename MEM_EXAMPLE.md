# Proposal: Neo4j Agent Memory Example

This proposal outlines adding a new example demonstrating how to use the Neo4j Context Provider for agent memory within the Microsoft Agent Framework.

## Background

The Microsoft Agent Framework provides a `ContextProvider` interface with two key lifecycle methods:
- **invoking()**: Called before each model invocation to retrieve and inject relevant context
- **invoked()**: Called after each model invocation to store or extract information from the conversation

Existing memory implementations (Mem0Provider, RedisProvider) demonstrate patterns for storing conversation history and retrieving relevant memories using search. The Neo4j Context Provider already supports vector and fulltext search with optional graph enrichment, making it well-suited for memory use cases—especially those requiring relationship-aware retrieval.

## Microsoft Agent Framework References

The following files in the Microsoft Agent Framework provide essential background for understanding and implementing memory functionality:

### Core Memory Interface
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/agent_framework/_memory.py` - Defines the `Context` class and `ContextProvider` abstract base class with `invoking()` and `invoked()` methods
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/agent_framework/_threads.py` - Defines `ChatMessageStoreProtocol` for persistent conversation storage

### Agent Integration
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/core/agent_framework/_agents.py` - Shows how context providers are called during agent execution (see `_prepare_thread_and_messages` method around line 1237)

### Memory Provider Implementations
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/mem0/agent_framework_mem0/_provider.py` - Mem0 memory provider implementation showing `invoking()` for search and `invoked()` for storage
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/redis/agent_framework_redis/_provider.py` - Redis memory provider with hybrid text and vector search
- `/Users/ryanknight/projects/azure/agent-framework/python/packages/redis/agent_framework_redis/_chat_message_store.py` - Redis-based conversation history storage

### Sample Implementations
- `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/context_providers/simple_context_provider.py` - Simple example showing user info extraction using LLM
- `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/context_providers/aggregate_context_provider.py` - Combining multiple providers
- `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/context_providers/mem0/mem0_basic.py` - Mem0 usage example
- `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/context_providers/redis/redis_basics.py` - Redis memory usage example
- `/Users/ryanknight/projects/azure/agent-framework/python/samples/getting_started/agents/azure_ai/azure_ai_with_memory_search.py` - Azure AI built-in memory search

## Proposed Example Structure

The example would be organized in two phases, each building on the previous:

---

## Phase 1: Basic Memory (Short-Term)

**Goal**: Demonstrate simple conversation memory using Neo4j's search capabilities.

**Concept**: Store conversation messages as nodes in Neo4j and retrieve relevant past messages using the existing index infrastructure (vector or fulltext). This mirrors how RedisProvider works but uses Neo4j as the storage backend.

**How It Works**:
1. After each model invocation, the provider stores user and assistant messages as `Memory` nodes in Neo4j
2. Each memory node includes the message text, role, timestamp, and scoping metadata (user_id, thread_id, agent_id)
3. Before each model invocation, the provider searches for relevant past memories using the current conversation as the query
4. Retrieved memories are injected as context, giving the agent awareness of past interactions

**Key Features**:
- Message text stored and indexed for semantic search
- Scoping filters ensure memories are retrieved only for the appropriate user/thread/agent
- Configurable retention (number of memories to store, time-based expiration)
- Works with both vector embeddings and fulltext search

**What This Enables**:
- Agent remembers facts shared in previous conversations
- Agent recalls user preferences mentioned earlier
- Agent maintains continuity across multiple interactions in the same thread

### Phase 1 Checklist

#### Provider Changes
- [ ] Implement `invoked()` method in `Neo4jContextProvider`
- [ ] Add message storage logic to write `Memory` nodes after each invocation
- [ ] Add scoping parameters (user_id, thread_id, agent_id) to provider configuration
- [ ] Add configuration for which message roles to store (user, assistant, or both)
- [ ] Add optional embedding generation for stored messages (for vector indexing)
- [ ] Add timestamp field to stored memories
- [ ] Update `invoking()` to filter retrieved memories by scoping parameters

#### Database Setup
- [ ] Define `Memory` node schema with required properties (text, role, timestamp, scoping fields)
- [ ] Create vector index on `Memory.embedding` (if using vector search)
- [ ] Create fulltext index on `Memory.text` (if using fulltext search)
- [ ] Create standard indexes on scoping fields for efficient filtering

#### Sample Application
- [ ] Create `samples/memory_basic/` directory
- [ ] Write demo script showing basic memory in action
- [ ] Write README with setup and usage instructions
- [ ] Add sample to the start-samples menu

#### Testing
- [ ] Verify memories are stored after each invocation
- [ ] Verify memories are retrieved based on conversation relevance
- [ ] Verify scoping filters work correctly (user A cannot see user B memories)
- [ ] Test with both vector and fulltext search modes

#### Documentation
- [ ] Update CLAUDE.md with memory configuration options
- [ ] Document new provider parameters
- [ ] Add memory example to main README

---

## Phase 2: Hierarchical Memory (Long-Term)

**Goal**: Demonstrate multi-level memory organization using Neo4j's graph capabilities for richer, more structured recall.

**Concept**: Build a memory hierarchy where raw messages are organized into higher-level abstractions (conversation summaries, topic clusters, user profiles). Graph relationships connect these layers, enabling traversal-based retrieval that provides both specific details and broader context.

**Memory Hierarchy**:

1. **Message Level** (Base Layer)
   - Individual user and assistant messages
   - Stored as `Memory` nodes with full text and metadata
   - Linked to their parent conversation via relationships

2. **Conversation Level** (Summary Layer)
   - Periodic summaries of conversation segments
   - Created when a conversation reaches a certain length or on explicit triggers
   - Stored as `ConversationSummary` nodes linked to the underlying messages
   - Captures key topics, decisions, and outcomes

3. **Topic Level** (Knowledge Layer)
   - Facts and entities extracted from conversations
   - Stored as domain-specific nodes (e.g., `Fact`, `Preference`, `Entity`)
   - Connected to conversations and other topics via typed relationships
   - Enables cross-conversation knowledge retrieval

4. **User Profile Level** (Aggregate Layer)
   - Long-term user preferences, patterns, and summary information
   - Periodically updated based on accumulated interactions
   - Stored as `UserProfile` nodes with structured attributes
   - Connected to topics and key facts

**Graph Relationships**:
- `(Memory)-[:PART_OF]->(Conversation)`
- `(ConversationSummary)-[:SUMMARIZES]->(Conversation)`
- `(Fact)-[:EXTRACTED_FROM]->(Memory)`
- `(UserProfile)-[:HAS_PREFERENCE]->(Preference)`
- `(Topic)-[:RELATED_TO]->(Topic)`

**How Retrieval Works**:
1. Initial search finds relevant memories at any level using vector or fulltext
2. Graph traversal expands context by following relationships
3. Retrieval query walks up the hierarchy (message → summary → topic) for broader context
4. Retrieval query walks down the hierarchy (topic → messages) for specific examples
5. Results combine immediate relevance with structural context

**What This Enables**:
- Agent accesses both specific memories and general knowledge about the user
- Agent understands how topics relate to each other
- Agent provides consistent responses based on established preferences
- Memory naturally organizes around meaningful structures rather than flat lists
- Old messages can be archived while preserving their summarized knowledge

### Phase 2 Checklist

#### Provider Changes
- [ ] Add summary generation hook to `invoked()` method
- [ ] Add configuration for summary trigger (message count, token count, or explicit)
- [ ] Add fact extraction hook (optional, LLM-based or pattern matching)
- [ ] Add user profile update logic
- [ ] Add hierarchy traversal queries to `invoking()` method
- [ ] Add configurable hierarchy depth setting
- [ ] Add memory consolidation method (merge old messages into summaries)
- [ ] Add memory cleanup/archival method

#### Database Setup
- [ ] Define `Conversation` node schema
- [ ] Define `ConversationSummary` node schema
- [ ] Define `Fact` node schema
- [ ] Define `Preference` node schema
- [ ] Define `UserProfile` node schema
- [ ] Create relationship types (PART_OF, SUMMARIZES, EXTRACTED_FROM, HAS_PREFERENCE, RELATED_TO)
- [ ] Create indexes on new node types for search
- [ ] Write Cypher queries for hierarchy traversal

#### Sample Application
- [ ] Create `samples/memory_hierarchical/` directory
- [ ] Write demo script showing hierarchical memory in action
- [ ] Write README with setup and usage instructions
- [ ] Add sample to the start-samples menu
- [ ] Create visualization showing memory graph structure

#### Testing
- [ ] Verify conversation summaries are generated at configured thresholds
- [ ] Verify facts are extracted and linked correctly
- [ ] Verify user profile updates based on accumulated data
- [ ] Verify hierarchy traversal returns appropriate context depth
- [ ] Verify memory consolidation preserves important information
- [ ] Test graph structure in Neo4j Browser

#### Documentation
- [ ] Document hierarchical memory configuration options
- [ ] Document summary generation settings
- [ ] Document fact extraction options
- [ ] Add architecture diagram showing memory hierarchy
- [ ] Update main README with hierarchical memory example

---

## Changes Required to the Provider

### Phase 1 Changes (Minimal)

The current Neo4j Context Provider focuses on retrieval (the `invoking()` method). For basic memory, we need to add:

1. **Implement the `invoked()` method**: Currently the provider does not implement this method. We need to add logic to store messages after each model invocation.

2. **Add message storage configuration**: New settings to control what gets stored:
   - Which message roles to store (user, assistant, or both)
   - Scoping fields (user_id, thread_id, agent_id) for multi-tenancy
   - Optional embedding generation for vector indexing

3. **Add a memory-specific node label**: Distinguish memory nodes from other content in the database (e.g., `Memory` label vs existing document chunks).

4. **Add timestamp and metadata fields**: Support time-based queries and memory management.

### Phase 2 Changes (Moderate)

For hierarchical memory, additional capabilities are needed:

1. **Summary generation hooks**: Integration points for generating conversation summaries (either via LLM calls or configurable summary logic).

2. **Fact extraction hooks**: Optional mechanism to extract structured facts from conversations (could use LLM or pattern matching).

3. **Hierarchy traversal queries**: New retrieval query templates that navigate the memory graph structure.

4. **Memory management utilities**: Functions to:
   - Consolidate old messages into summaries
   - Update user profiles based on accumulated data
   - Archive or prune stale memories while preserving summaries

5. **Configurable hierarchy depth**: Settings to control how many levels of the hierarchy to traverse during retrieval.

## Example Organization

The examples would be added to the `samples/` directory:

```
samples/
├── memory_basic/           # Phase 1: Basic memory
│   ├── demo.py             # Simple memory demonstration
│   └── README.md           # Setup and usage instructions
├── memory_hierarchical/    # Phase 2: Hierarchical memory
│   ├── demo.py             # Graph-based memory demonstration
│   └── README.md           # Setup and usage instructions
└── shared/
    └── memory_setup.py     # Common memory schema setup utilities
```

## Database Schema

### Phase 1 Schema

Nodes:
- `Memory` - Individual stored messages with text, role, timestamp, embeddings

Indexes:
- Vector index on `Memory.embedding` for semantic search
- Fulltext index on `Memory.text` for keyword search
- Standard indexes on scoping fields for filtering

### Phase 2 Schema (Additions)

Nodes:
- `Conversation` - Groups of related messages
- `ConversationSummary` - Summaries of conversation segments
- `Fact` - Extracted factual information
- `Preference` - User preferences
- `UserProfile` - Aggregate user information

Relationships:
- `PART_OF` - Message belongs to conversation
- `SUMMARIZES` - Summary covers a conversation
- `EXTRACTED_FROM` - Fact came from a message
- `HAS_PREFERENCE` - User has a preference
- `RELATED_TO` - Topics or facts relate to each other

## Success Criteria

Phase 1:
- Agent correctly recalls information from previous conversations
- Memory is properly scoped to user/thread
- Search retrieves relevant memories based on current conversation
- Example is straightforward to understand and adapt

Phase 2:
- Agent accesses appropriate level of detail based on query
- Graph traversal enriches context with related information
- Summaries reduce token usage while preserving key information
- Memory hierarchy is visible and understandable in Neo4j browser

## Dependencies

- Existing Neo4j Context Provider infrastructure
- Neo4j database with appropriate indexes
- Azure AI embeddings (for vector-based memory)
- Optional: LLM access for summary/fact extraction in Phase 2

## Open Questions

1. How should summary generation be triggered (token count, message count, explicit call)?
2. What fact extraction approach works best for general use cases?
3. How should memory retention and cleanup be handled?
4. Should the hierarchical memory support custom schema extensions for domain-specific use cases?

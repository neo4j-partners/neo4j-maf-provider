# Samples Setup Guide

This guide covers setting up the Neo4j databases and Azure infrastructure required to run the sample applications.

## Prerequisites

- [UV](https://docs.astral.sh/uv/) package manager
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) with `azd` extension
- [Neo4j Aura](https://neo4j.com/cloud/aura/) account (or self-hosted Neo4j 5.x+)
- Azure subscription with access to Azure AI services

## Quick Start

```bash
# 1. Install dependencies
uv sync --prerelease=allow

# 2. Deploy Azure infrastructure
cd samples
azd up

# 3. Sync Azure environment variables
uv run setup_env.py

# 4. Add Neo4j credentials to .env (see sections below)

# 5. Run samples
uv run start-samples
```

## Sample Overview

| Demo | Name | Database | Index Type |
|------|------|----------|------------|
| 1 | Azure Thread Memory | None | N/A |
| 2 | Semantic Search | Financial | Vector |
| 3 | Context Provider (Fulltext) | Financial | Fulltext |
| 4 | Context Provider (Vector) | Financial | Vector |
| 5 | Context Provider (Graph-Enriched) | Financial | Vector |
| 6 | Maintenance Search | Aircraft | Fulltext |
| 7 | Flight Delay Analysis | Aircraft | Fulltext |
| 8 | Component Health Analysis | Aircraft | Fulltext |

---

## Azure Infrastructure Setup

### 1. Deploy with Azure Developer CLI

```bash
cd samples
azd up
```

This provisions:
- Azure AI Services (GPT-4o chat model)
- Azure OpenAI (text-embedding-ada-002 embeddings)
- Microsoft Foundry project

### 2. Sync Environment Variables

```bash
uv run setup_env.py
```

This pulls Azure variables into `.env` while preserving your Neo4j credentials.

### Required Azure Variables

These are automatically set by `setup_env.py`:

```
AZURE_AI_PROJECT_ENDPOINT     # Microsoft Foundry endpoint
AZURE_AI_MODEL_NAME           # Chat model (default: gpt-4o)
AZURE_AI_EMBEDDING_NAME       # Embedding model (default: text-embedding-ada-002)
```

---

## Financial Documents Database (Samples 2-5)

### Graph Schema

```
(:Company {name, ticker})
(:Document {title})
(:Chunk {text, embedding})
(:RiskFactor {name})
(:Product {name})

(:Chunk)-[:FROM_DOCUMENT]->(:Document)
(:Company)-[:FILED]->(:Document)
(:Company)-[:FACES_RISK]->(:RiskFactor)
(:Company)-[:MENTIONS]->(:Product)
```

### Required Data

- SEC filing documents from companies (e.g., Microsoft, Apple, Amazon)
- Document chunks with text content
- Vector embeddings generated for each chunk (using Azure AI embeddings)
- Company metadata with ticker symbols
- Risk factors and products associated with companies

### Create Indexes

Run in Neo4j Browser or Cypher shell:

```cypher
-- Fulltext index for keyword search (Sample 3)
CREATE FULLTEXT INDEX search_chunks IF NOT EXISTS
FOR (c:Chunk) ON EACH [c.text];

-- Vector index for semantic search (Samples 2, 4, 5)
CREATE VECTOR INDEX chunkEmbeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};
```

### Generate Embeddings

Chunks need embeddings populated before vector search works. Example approach:

```cypher
-- After generating embeddings via Azure AI, update chunks
MATCH (c:Chunk)
WHERE c.embedding IS NULL
SET c.embedding = $embedding  -- 1536-dimension vector from text-embedding-ada-002
```

### Sample Data (Cypher)

Minimal example to get started:

```cypher
CREATE (msft:Company {name: 'Microsoft Corporation', ticker: 'MSFT'})
CREATE (doc:Document {title: 'Microsoft 10-K Annual Report 2023'})
CREATE (chunk:Chunk {text: 'Microsoft offers a wide range of cloud computing services through Azure, including virtual machines, databases, and AI services.'})
CREATE (risk:RiskFactor {name: 'Cybersecurity threats'})
CREATE (product:Product {name: 'Azure'})

CREATE (chunk)-[:FROM_DOCUMENT]->(doc)
CREATE (msft)-[:FILED]->(doc)
CREATE (msft)-[:FACES_RISK]->(risk)
CREATE (msft)-[:MENTIONS]->(product);
```

### Environment Variables

Add to `samples/.env`:

```
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_VECTOR_INDEX_NAME=chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME=search_chunks
```

---

## Aircraft Domain Database (Samples 6-8)

### Graph Schema

```
(:Aircraft {tail_number, model})
(:System {name, type})
(:Component {name, type})
(:MaintenanceEvent {fault, corrective_action, severity})
(:Flight {flight_number})
(:Delay {cause, minutes})
(:Airport {name, city, iata})

(:Aircraft)-[:HAS_SYSTEM]->(:System)
(:System)-[:HAS_COMPONENT]->(:Component)
(:Component)-[:HAS_EVENT]->(:MaintenanceEvent)
(:Aircraft)<-[:OPERATES_FLIGHT]-(:Flight)
(:Flight)-[:DEPARTS_FROM]->(:Airport)
(:Flight)-[:ARRIVES_AT]->(:Airport)
(:Flight)-[:HAS_DELAY]->(:Delay)
```

### Required Data

- Aircraft with tail numbers and models
- Systems (hydraulic, electrical, pneumatic, etc.)
- Components within each system
- Maintenance events with fault descriptions and corrective actions
- Flights with delays and route information
- Airports with IATA codes

### Create Indexes

Run the setup script:

```bash
uv run python scripts/setup_aircraft_indexes.py
```

This creates four fulltext indexes:
- `maintenance_search` on MaintenanceEvent (fault, corrective_action)
- `component_search` on Component (name, type)
- `airport_search` on Airport (name, city)
- `delay_search` on Delay (cause)

Or create manually:

```cypher
CREATE FULLTEXT INDEX maintenance_search IF NOT EXISTS
FOR (m:MaintenanceEvent) ON EACH [m.fault, m.corrective_action];

CREATE FULLTEXT INDEX component_search IF NOT EXISTS
FOR (c:Component) ON EACH [c.name, c.type];

CREATE FULLTEXT INDEX airport_search IF NOT EXISTS
FOR (a:Airport) ON EACH [a.name, a.city];

CREATE FULLTEXT INDEX delay_search IF NOT EXISTS
FOR (d:Delay) ON EACH [d.cause];
```

### Sample Data (Cypher)

Minimal example to get started:

```cypher
// Aircraft with systems and components
CREATE (ac:Aircraft {tail_number: 'N12345', model: 'Boeing 737-800'})
CREATE (hyd:System {name: 'Main Hydraulic System', type: 'hydraulic'})
CREATE (pump:Component {name: 'Hydraulic Pump A', type: 'pump'})
CREATE (event:MaintenanceEvent {
  fault: 'Hydraulic pressure fluctuation detected during flight',
  corrective_action: 'Replaced hydraulic pump seals and tested system',
  severity: 'moderate'
})

CREATE (ac)-[:HAS_SYSTEM]->(hyd)
CREATE (hyd)-[:HAS_COMPONENT]->(pump)
CREATE (pump)-[:HAS_EVENT]->(event)

// Flight with delay
CREATE (lax:Airport {name: 'Los Angeles International', city: 'Los Angeles', iata: 'LAX'})
CREATE (jfk:Airport {name: 'John F Kennedy International', city: 'New York', iata: 'JFK'})
CREATE (flight:Flight {flight_number: 'AA100'})
CREATE (delay:Delay {cause: 'Weather - thunderstorms at destination', minutes: 45})

CREATE (flight)-[:OPERATES_FLIGHT]->(ac)
CREATE (flight)-[:DEPARTS_FROM]->(lax)
CREATE (flight)-[:ARRIVES_AT]->(jfk)
CREATE (flight)-[:HAS_DELAY]->(delay);
```

### Environment Variables

Add to `samples/.env`:

```
AIRCRAFT_NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
AIRCRAFT_NEO4J_USERNAME=neo4j
AIRCRAFT_NEO4J_PASSWORD=your-password
```

---

## Complete .env Example

```bash
# Azure (auto-populated by setup_env.py)
AZURE_AI_PROJECT_ENDPOINT=https://your-project.cognitiveservices.azure.com
AZURE_AI_MODEL_NAME=gpt-4o
AZURE_AI_EMBEDDING_NAME=text-embedding-ada-002

# Financial Documents Database (Samples 2-5)
NEO4J_URI=neo4j+s://financial.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-financial-db-password
NEO4J_VECTOR_INDEX_NAME=chunkEmbeddings
NEO4J_FULLTEXT_INDEX_NAME=search_chunks

# Aircraft Domain Database (Samples 6-8)
AIRCRAFT_NEO4J_URI=neo4j+s://aircraft.databases.neo4j.io
AIRCRAFT_NEO4J_USERNAME=neo4j
AIRCRAFT_NEO4J_PASSWORD=your-aircraft-db-password
```

---

## Verification

### Check Neo4j Indexes

```cypher
SHOW INDEXES;
```

Ensure indexes show `state: ONLINE`.

### Test Financial Database

```cypher
-- Test fulltext index
CALL db.index.fulltext.queryNodes('search_chunks', 'Microsoft')
YIELD node, score RETURN node.text, score LIMIT 3;

-- Test vector index (requires embedding)
CALL db.index.vector.queryNodes('chunkEmbeddings', 5, $embedding)
YIELD node, score RETURN node.text, score;
```

### Test Aircraft Database

```bash
uv run python scripts/setup_aircraft_indexes.py
```

This verifies indexes exist and runs test queries.

---

## Running Samples

```bash
# Interactive menu
uv run start-samples

# Run specific demo
uv run start-samples 3    # Fulltext search demo

# Run all demos
uv run start-samples a
```

---

## Troubleshooting

### "Neo4j not configured"

Add the required Neo4j environment variables to `.env`. The samples check for:
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (financial database)
- `AIRCRAFT_NEO4J_URI`, `AIRCRAFT_NEO4J_USERNAME`, `AIRCRAFT_NEO4J_PASSWORD` (aircraft database)

### "Azure not configured"

Run `azd up` followed by `uv run setup_env.py` to populate Azure variables.

### "Index not found"

Create the required indexes as shown above. Vector indexes require embeddings to be populated on nodes.

### "No results returned"

- Verify data exists in the database
- Check index names match environment variables
- For vector search, ensure chunks have `embedding` property populated

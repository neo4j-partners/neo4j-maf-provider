#!/bin/bash
# Neo4j Structured Data Load Script
# Loads financial-data/Asset_Manager_Holdings.csv and Company_Filings.csv into Neo4j
#
# Usage: ./scripts/load_data.sh
#
# Loads credentials from .env (project root) automatically.
# Environment variables can override .env values:
#   NEO4J_URI      - Neo4j connection URI
#   NEO4J_USERNAME - Neo4j username
#   NEO4J_PASSWORD - Neo4j password
#   CSV_BASE_URL   - Base URL for CSV files (default: file:/// + script directory)

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env from project root if it exists
ENV_FILE="${PROJECT_ROOT}/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading credentials from ${ENV_FILE}"
    # Export NEO4J_* variables from .env
    while IFS= read -r line; do
        if [[ "$line" =~ ^NEO4J_ ]]; then
            export "$line"
        fi
    done < "$ENV_FILE"
fi

# Configuration with defaults
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"

# Check for required password
if [ -z "$NEO4J_PASSWORD" ]; then
    echo "Error: NEO4J_PASSWORD not found"
    echo "Either set it in ${ENV_FILE} or export NEO4J_PASSWORD=yourpassword"
    exit 1
fi

# Determine CSV base URL based on Neo4j connection type
# Neo4j Aura (cloud) can't access file:// URLs, so use GitHub raw URLs
GITHUB_RAW_URL="https://raw.githubusercontent.com/neo4j-partners/workshop-financial-data/refs/heads/main"

if [[ "$NEO4J_URI" == *"neo4j+s://"* ]] || [[ "$NEO4J_URI" == *"databases.neo4j.io"* ]]; then
    CSV_BASE_URL="${CSV_BASE_URL:-$GITHUB_RAW_URL}"
    echo "Detected Neo4j Aura - using GitHub URLs for CSV files"
else
    CSV_BASE_URL="${CSV_BASE_URL:-file://${PROJECT_ROOT}/financial-data}"
fi

# CSV file URLs
ASSET_MANAGER_URL="${CSV_BASE_URL}/Asset_Manager_Holdings.csv"
COMPANY_FILINGS_URL="${CSV_BASE_URL}/Company_Filings.csv"

echo "=== Neo4j Structured Data Loader ==="
echo "Neo4j URI: ${NEO4J_URI}"
echo "CSV Base URL: ${CSV_BASE_URL}"
echo ""

# Function to run cypher
run_cypher() {
    local description="$1"
    local cypher="$2"
    echo ">>> ${description}..."
    echo "$cypher" | cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USERNAME" -p "$NEO4J_PASSWORD" --format plain
}

# Step 1: Create constraints
echo "=== Creating Constraints ==="

run_cypher "Creating AssetManager constraint" \
"CREATE CONSTRAINT asset_manager_name IF NOT EXISTS
FOR (a:AssetManager) REQUIRE a.managerName IS UNIQUE;"

run_cypher "Creating Company constraint" \
"CREATE CONSTRAINT company_name IF NOT EXISTS
FOR (c:Company) REQUIRE c.name IS UNIQUE;"

run_cypher "Creating Document constraint" \
"CREATE CONSTRAINT document_path IF NOT EXISTS
FOR (d:Document) REQUIRE d.path IS UNIQUE;"

echo ""
echo "=== Loading Nodes ==="

# Step 2: Load Company nodes
run_cypher "Loading Company nodes" \
"LOAD CSV WITH HEADERS FROM '${COMPANY_FILINGS_URL}' AS row
MERGE (c:Company {name: row.name})
SET c.ticker = row.ticker;"

# Step 3: Load Document nodes
run_cypher "Loading Document nodes" \
"LOAD CSV WITH HEADERS FROM '${COMPANY_FILINGS_URL}' AS row
MERGE (d:Document {path: row.path_Mac_ix});"

# Step 4: Load AssetManager nodes
run_cypher "Loading AssetManager nodes" \
"LOAD CSV WITH HEADERS FROM '${ASSET_MANAGER_URL}' AS row
MERGE (a:AssetManager {managerName: row.managerName});"

echo ""
echo "=== Creating Relationships ==="

# Step 5: Create FILED relationships
run_cypher "Creating FILED relationships" \
"LOAD CSV WITH HEADERS FROM '${COMPANY_FILINGS_URL}' AS row
MATCH (c:Company {name: row.name})
MATCH (d:Document {path: row.path_Mac_ix})
MERGE (c)-[:FILED]->(d);"

# Step 6: Create OWNS relationships
run_cypher "Creating OWNS relationships" \
"LOAD CSV WITH HEADERS FROM '${ASSET_MANAGER_URL}' AS row
MATCH (a:AssetManager {managerName: row.managerName})
MATCH (c:Company {name: row.companyName})
MERGE (a)-[r:OWNS]->(c)
SET r.shares = toInteger(row.shares);"

echo ""
echo "=== Load Complete ==="
echo ""

# Show summary - using modern Cypher best practices
run_cypher "Nodes by label" \
"MATCH (n)
WITH labels(n)[0] AS Label
WHERE Label IS NOT NULL
WITH Label, count(*) AS Count
RETURN Label, Count
ORDER BY Label;"

run_cypher "Relationships by type" \
"MATCH ()-[r]->()
WITH type(r) AS Type
WHERE Type IS NOT NULL
WITH Type, count(*) AS Count
RETURN Type, Count
ORDER BY Type;"

run_cypher "Total nodes and relationships" \
"CALL {
  MATCH (n) RETURN count(n) AS nodes
}
CALL {
  MATCH ()-[r]->() RETURN count(r) AS rels
}
RETURN nodes AS TotalNodes, rels AS TotalRelationships;"

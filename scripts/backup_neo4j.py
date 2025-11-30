#!/usr/bin/env python3
"""
Neo4j Database Backup Script

Backs up the Neo4j database to a JSON file.
Uses APOC streaming export to retrieve all nodes and relationships.

Usage:
    uv run python scripts/backup_neo4j.py /path/to/snapshot/directory
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from neo4j import AsyncDriver, AsyncSession


class BackupConfig(BaseSettings):
    """Configuration for Neo4j backup loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    uri: str | None = Field(default=None, validation_alias="NEO4J_URI")
    username: str | None = Field(default=None, validation_alias="NEO4J_USERNAME")
    password: str | None = Field(default=None, validation_alias="NEO4J_PASSWORD")
    vector_index_name: str | None = Field(default=None, validation_alias="NEO4J_VECTOR_INDEX_NAME")

    @property
    def is_configured(self) -> bool:
        return all([self.uri, self.username, self.password])


def get_project_root() -> Path:
    return Path(__file__).parent.parent


async def get_database_stats(session: AsyncSession, vector_index_name: str | None) -> dict:
    """Get database statistics including node count, relationship count, and embeddings."""
    stats: dict = {
        "nodes": 0,
        "relationships": 0,
        "embeddings": 0,
        "vector_index_name": vector_index_name,
    }

    # Count nodes
    result = await session.run("MATCH (n) RETURN count(*) AS count")
    record = await result.single()
    stats["nodes"] = record["count"]

    # Count relationships
    result = await session.run("MATCH ()-->() RETURN count(*) AS count")
    record = await result.single()
    stats["relationships"] = record["count"]

    # Count embeddings if vector index is configured
    if vector_index_name:
        try:
            result = await session.run(
                "SHOW INDEXES YIELD name, type, labelsOrTypes, properties "
                "WHERE name = $index_name AND type = 'VECTOR' "
                "RETURN labelsOrTypes, properties",
                {"index_name": vector_index_name},
            )
            record = await result.single()

            if record:
                labels = record["labelsOrTypes"]
                props = record["properties"]
                if labels and props:
                    label = labels[0]
                    prop = props[0]
                    # Use parameterized query pattern for safety
                    count_result = await session.run(
                        "MATCH (n) WHERE $label IN labels(n) AND n[$prop] IS NOT NULL "
                        "RETURN count(*) AS count",
                        {"label": label, "prop": prop},
                    )
                    count_record = await count_result.single()
                    stats["embeddings"] = count_record["count"]
            else:
                print(f"Warning: Vector index '{vector_index_name}' not found")
        except Exception as e:
            print(f"Warning: Could not get embeddings count: {e}")

    return stats


async def get_database_schema(session: AsyncSession) -> dict:
    """Export all indexes and constraints from the database."""
    schema: dict = {"indexes": [], "constraints": []}

    # Get indexes (excluding system LOOKUP indexes)
    result = await session.run(
        "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options "
        "WHERE type <> 'LOOKUP' "
        "RETURN name, type, labelsOrTypes, properties, options"
    )
    records = await result.data()

    for record in records:
        schema["indexes"].append({
            "name": record["name"],
            "type": record["type"],
            "labels": record["labelsOrTypes"],
            "properties": record["properties"],
            "options": record["options"],
        })

    # Get constraints
    result = await session.run(
        "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties "
        "RETURN name, type, labelsOrTypes, properties"
    )
    records = await result.data()

    for record in records:
        schema["constraints"].append({
            "name": record["name"],
            "type": record["type"],
            "labels": record["labelsOrTypes"],
            "properties": record["properties"],
        })

    return schema


async def check_apoc_available(session: AsyncSession) -> str | None:
    """Check if APOC is available and return version, or None if not available."""
    try:
        result = await session.run("RETURN apoc.version() AS version")
        record = await result.single()
        return record["version"]
    except Exception:
        return None


async def backup_via_apoc(session: AsyncSession) -> dict:
    """Back up the Neo4j database using APOC streaming export."""
    print("Starting APOC streaming export...")
    result = await session.run(
        "CALL apoc.export.json.all(null, {useTypes: true, stream: true}) "
        "YIELD file, nodes, relationships, properties, data "
        "RETURN nodes, relationships, properties, data"
    )
    record = await result.single()

    return {
        "nodes": record["nodes"],
        "relationships": record["relationships"],
        "properties": record["properties"],
        "data": record["data"],
    }


async def backup_via_cypher(session: AsyncSession) -> dict:
    """Fallback backup method using plain Cypher queries.

    Produces newline-delimited JSON matching APOC export format for compatibility
    with the restore script.
    """
    lines: list[str] = []
    node_count = 0
    rel_count = 0
    prop_count = 0

    # Export nodes in batches to avoid OOM on large databases
    print("Exporting nodes...")
    skip = 0
    batch_size = 1000

    while True:
        result = await session.run(
            "MATCH (n) "
            "RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS properties "
            "SKIP $skip LIMIT $limit",
            {"skip": skip, "limit": batch_size},
        )
        records = await result.data()

        if not records:
            break

        for record in records:
            # Format matching APOC export: {"type":"node","id":"...","labels":[...],"properties":{...}}
            node_obj = {
                "type": "node",
                "id": record["id"],
                "labels": record["labels"],
                "properties": record["properties"],
            }
            lines.append(json.dumps(node_obj, default=str))
            node_count += 1
            prop_count += len(record.get("properties", {}))

        skip += batch_size
        if node_count % 5000 == 0:
            print(f"  Exported {node_count} nodes...")

    print(f"  Total: {node_count} nodes")

    # Export relationships in batches
    print("Exporting relationships...")
    skip = 0

    while True:
        result = await session.run(
            "MATCH (a)-[r]->(b) "
            "RETURN elementId(r) AS id, type(r) AS type, "
            "elementId(a) AS startId, elementId(b) AS endId, "
            "properties(r) AS properties "
            "SKIP $skip LIMIT $limit",
            {"skip": skip, "limit": batch_size},
        )
        records = await result.data()

        if not records:
            break

        for record in records:
            # Format matching APOC export: {"type":"relationship","id":"...","label":"...","start":{"id":"..."},"end":{"id":"..."},"properties":{...}}
            rel_obj = {
                "type": "relationship",
                "id": record["id"],
                "label": record["type"],
                "start": {"id": record["startId"]},
                "end": {"id": record["endId"]},
                "properties": record["properties"],
            }
            lines.append(json.dumps(rel_obj, default=str))
            rel_count += 1

        skip += batch_size
        if rel_count % 5000 == 0:
            print(f"  Exported {rel_count} relationships...")

    print(f"  Total: {rel_count} relationships")

    # Join with newlines for newline-delimited JSON format
    data = "\n".join(lines)

    return {
        "nodes": node_count,
        "relationships": rel_count,
        "properties": prop_count,
        "data": data,
    }


async def backup_database(session: AsyncSession) -> dict:
    """Back up the Neo4j database, using APOC if available, otherwise Cypher fallback."""
    apoc_version = await check_apoc_available(session)

    if apoc_version:
        print(f"APOC version: {apoc_version}")
        return await backup_via_apoc(session)
    else:
        print("Warning: APOC not available, using Cypher-based export")
        return await backup_via_cypher(session)


def write_checksum_file(checksum_path: Path, stats: dict, schema: dict) -> None:
    """Write database statistics and schema to a checksum file."""
    checksum_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nodes": stats["nodes"],
        "relationships": stats["relationships"],
        "embeddings": stats["embeddings"],
        "vector_index_name": stats["vector_index_name"],
        "schema": schema,
    }
    with open(checksum_path, "w", encoding="utf-8") as f:
        json.dump(checksum_data, f, indent=2)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Back up Neo4j database to JSON file.")
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to save backup files (financial_backup.json and financial_backup.checksum.json)",
    )
    return parser.parse_args()


async def main() -> int:
    """Main entry point for the backup script."""
    args = parse_args()

    env_path = get_project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        print(f"Warning: {env_path} not found")

    config = BackupConfig()
    if not config.is_configured:
        print("Error: Neo4j configuration incomplete.")
        print("Required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        return 1

    backup_dir = Path(args.directory).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_file = backup_dir / "financial_backup.json"
    checksum_file = backup_dir / "financial_backup.checksum.json"

    print("=== Neo4j Database Backup ===")
    print(f"Target: {backup_file}")
    print()

    # Create a single driver instance for all operations
    driver: AsyncDriver = AsyncGraphDatabase.driver(
        config.uri, auth=(config.username, config.password)
    )

    try:
        await driver.verify_connectivity()
        print(f"Connected to Neo4j at {config.uri}")
        print()

        async with driver.session() as session:
            print("Getting database statistics...")
            stats = await get_database_stats(session, config.vector_index_name)
            print(f"  Nodes: {stats['nodes']}")
            print(f"  Relationships: {stats['relationships']}")
            if config.vector_index_name:
                print(f"  Embeddings ({config.vector_index_name}): {stats['embeddings']}")
            print()

            print("Exporting schema...")
            schema = await get_database_schema(session)
            print(f"  Indexes: {len(schema['indexes'])}")
            print(f"  Constraints: {len(schema['constraints'])}")
            print()

            result = await backup_database(session)

        # Write backup file
        with open(backup_file, "w", encoding="utf-8") as f:
            f.write(result["data"])

        # Write checksum file
        write_checksum_file(checksum_file, stats, schema)

        print()
        print("=== Backup Complete ===")
        print(f"Nodes: {result['nodes']}")
        print(f"Relationships: {result['relationships']}")
        print(f"Properties: {result['properties']}")
        print(f"Indexes: {len(schema['indexes'])}")
        print(f"Constraints: {len(schema['constraints'])}")
        print(f"Backup saved to: {backup_file}")
        print(f"Checksum saved to: {checksum_file}")
        return 0

    except Exception as e:
        print(f"Error: Backup failed - {e}")
        return 1
    finally:
        await driver.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

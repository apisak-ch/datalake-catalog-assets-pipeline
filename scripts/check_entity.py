"""
check_entity.py

Read-only lookup: checks whether one or more entities already exist in
OpenMetadata, by fully qualified name (FQN). Use this before assuming an
upstream table/container/pipeline/topic is already cataloged -- e.g. before
drafting a lineage config that points at it, or before deciding a
create_*.py config can skip creating it.

Makes GET requests only. Never creates, updates, or deletes anything.

Usage:
    python scripts/check_entity.py <entity_type> <fqn> [<fqn> ...]

    entity_type is one of: table, container, pipeline, topic, database, schema

Examples:
    python scripts/check_entity.py table hive.prod.prod_safe_mymo.register hive.prod.prod_safe_mymo.deactivation
    python scripts/check_entity.py container hdfs.prod.gold_safe.datalake_gold_safe
    python scripts/check_entity.py pipeline airflow.mymo_register_data_extraction

Exit code is non-zero if any of the given FQNs was not found, so this can
also be used as a precondition check in a shell pipeline.
"""

import os
import sys

import requests
from dotenv import load_dotenv

# --- Configuration: loaded from .env in the repo root (see .env.example) ---
load_dotenv()
OPENMETADATA_HOST = os.environ["OPENMETADATA_HOST"]
OPENMETADATA_TOKEN = os.environ["OPENMETADATA_TOKEN"]
# -----------------------------------------------------------

HEADERS = {
    "Authorization": f"Bearer {OPENMETADATA_TOKEN}",
}

# Maps the CLI's entity_type argument to its OpenMetadata REST collection.
COLLECTIONS = {
    "table": "tables",
    "container": "containers",
    "pipeline": "pipelines",
    "topic": "topics",
    "database": "databases",
    "schema": "databaseSchemas",
}


def check(collection: str, fqn: str) -> bool:
    """GETs the entity by FQN. Returns True if found (200), False if not
    found (404). Any other status code is treated as an error and raised,
    since it likely means a bad host/token rather than a missing entity."""
    url = f"{OPENMETADATA_HOST}/v1/{collection}/name/{fqn}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    print(f"  UNEXPECTED ({resp.status_code}) checking {fqn}: {resp.text}")
    resp.raise_for_status()


def main(entity_type: str, fqns: list[str]) -> None:
    if entity_type not in COLLECTIONS:
        print(f"Unknown entity_type '{entity_type}'. Choose from: {', '.join(COLLECTIONS)}")
        sys.exit(1)

    collection = COLLECTIONS[entity_type]
    all_found = True
    for fqn in fqns:
        found = check(collection, fqn)
        print(f"{'EXISTS  ' if found else 'NOT FOUND'}: {entity_type} {fqn}")
        all_found = all_found and found

    sys.exit(0 if all_found else 1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/check_entity.py <entity_type> <fqn> [<fqn> ...]")
        print(f"  entity_type is one of: {', '.join(COLLECTIONS)}")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2:])

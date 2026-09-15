"""
disconnect_lineage.py

Deletes lineage edges from OpenMetadata -- the counterpart to
connect_lineage.py. Uses the same JSON config format (scheduler_lineage_config.json),
resolving each fromEntity/toEntity FQN to its ID the same way, then calls
DELETE instead of PUT.

Usage:
    python scripts/disconnect_lineage.py configs/scheduler_service_journal_data_extraction/scheduler_lineage_config.json

NOTE: this only removes the edges listed in the config. It does not
delete the entities themselves (topics, tables, pipelines, containers).
"""

import json
import os
import sys
from urllib.parse import quote

import requests
from dotenv import load_dotenv

# --- Configuration: loaded from .env in the repo root (see .env.example) ---
load_dotenv()
OPENMETADATA_HOST = os.environ["OPENMETADATA_HOST"]
OPENMETADATA_TOKEN = os.environ["OPENMETADATA_TOKEN"]
# -----------------------------------------------------------

HEADERS = {
    "Authorization": f"Bearer {OPENMETADATA_TOKEN}",
    "Content-Type": "application/json",
}

TYPE_TO_COLLECTION = {
    "table": "tables",
    "pipeline": "pipelines",
    "dashboard": "dashboards",
    "topic": "topics",
    "mlmodel": "mlmodels",
    "container": "containers",
    "searchIndex": "searchIndexes",
}


def get_entity_id(entity_type: str, fqn: str) -> str:
    """Resolve a fully-qualified name to its entity UUID."""
    collection = TYPE_TO_COLLECTION.get(entity_type)
    if not collection:
        raise ValueError(f"Unknown entity type '{entity_type}'. Add it to TYPE_TO_COLLECTION.")
    url = f"{OPENMETADATA_HOST}/v1/{collection}/name/{quote(fqn, safe='')}"
    resp = requests.get(url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code != 200:
        print(f"  FAILED to resolve {entity_type} '{fqn}' ({resp.status_code}): {resp.text}")
        resp.raise_for_status()
    return resp.json()["id"]


def delete_edge(edge: dict) -> None:
    from_type, from_fqn = edge["fromEntity"]["type"], edge["fromEntity"]["fqn"]
    to_type, to_fqn = edge["toEntity"]["type"], edge["toEntity"]["fqn"]

    from_id = get_entity_id(from_type, from_fqn)
    to_id = get_entity_id(to_type, to_fqn)

    url = f"{OPENMETADATA_HOST}/v1/lineage/{from_type}/{from_id}/{to_type}/{to_id}"
    resp = requests.delete(url, headers=HEADERS, timeout=30)
    if resp.status_code not in (200, 204):
        print(f"  FAILED ({resp.status_code}): {from_fqn} -> {to_fqn}: {resp.text}")
        resp.raise_for_status()

    print(f"Deleted lineage: {from_fqn} -> {to_fqn}")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for edge in config["edges"]:
        delete_edge(edge)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/disconnect_lineage.py configs/scheduler_service_journal_data_extraction/scheduler_lineage_config.json")
        sys.exit(1)
    main(sys.argv[1])

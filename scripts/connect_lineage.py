"""
connect_lineage.py

A generic, config-driven framework for creating data lineage edges in
OpenMetadata from a JSON file -- same idea as create_db_asset.py, but for
lineage instead of entities.

Rather than calling the Lineage API directly with raw entity UUIDs,
describe each edge in a JSON config using fully-qualified names (FQNs) --
the same ones you already see in the OpenMetadata UI/URLs, e.g.
"manual-pilot.uat_safe_fraud.default.source_transaction_logs". The script
resolves each FQN to its entity ID at runtime, then creates the edge.

Usage:
    python scripts/connect_lineage.py configs/scheduler_service_journal_data_extraction/scheduler_lineage_config.json

Idempotency: the Lineage API is called with PUT, so re-running the same
config repeatedly is safe -- edges aren't duplicated, just re-confirmed.

NOTE: column-level lineage (columnLineage) and sqlQuery are only
supported for table-to-table edges. Edges involving pipelines,
dashboards, etc. can still be created, just without column detail.
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

# Maps the "type" you write in the config to its REST collection name.
# Extend this if you need lineage on other entity types.
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


def build_column_lineage(from_fqn: str, to_fqn: str, column_defs: list) -> list:
    """Turn short column names in the config into the full column FQNs
    the API expects (<table_fqn>.<column_name>)."""
    result = []
    for col in column_defs:
        from_columns = col.get("fromColumns") or [col["fromColumn"]]
        result.append({
            "fromColumns": [f"{from_fqn}.{c}" for c in from_columns],
            "toColumn": f"{to_fqn}.{col['toColumn']}",
            "function": col.get("function", "DIRECT"),
        })
    return result


def create_edge(edge: dict) -> None:
    from_type, from_fqn = edge["fromEntity"]["type"], edge["fromEntity"]["fqn"]
    to_type, to_fqn = edge["toEntity"]["type"], edge["toEntity"]["fqn"]

    from_id = get_entity_id(from_type, from_fqn)
    to_id = get_entity_id(to_type, to_fqn)

    payload = {
        "edge": {
            "fromEntity": {"id": from_id, "type": from_type},
            "toEntity": {"id": to_id, "type": to_type},
        }
    }

    if edge.get("description"):
        payload["edge"]["description"] = edge["description"]

    lineage_details = {}
    if edge.get("pipeline"):
        pipeline_type, pipeline_fqn = edge["pipeline"]["type"], edge["pipeline"]["fqn"]
        pipeline_id = get_entity_id(pipeline_type, pipeline_fqn)
        lineage_details["pipeline"] = {"id": pipeline_id, "type": pipeline_type}
    if edge.get("sqlQuery"):
        lineage_details["sqlQuery"] = edge["sqlQuery"]
    if edge.get("columnLineage"):
        lineage_details["columnsLineage"] = build_column_lineage(from_fqn, to_fqn, edge["columnLineage"])
    if lineage_details:
        payload["edge"]["lineageDetails"] = lineage_details

    url = f"{OPENMETADATA_HOST}/v1/lineage"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {from_fqn} -> {to_fqn}: {resp.text}")
        resp.raise_for_status()

    pipeline_note = f" (via {edge['pipeline']['fqn']})" if edge.get("pipeline") else ""
    print(f"Lineage: {from_fqn} -> {to_fqn}{pipeline_note}")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for edge in config["edges"]:
        create_edge(edge)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/connect_lineage.py configs/scheduler_service_journal_data_extraction/scheduler_lineage_config.json")
        sys.exit(1)
    main(sys.argv[1])

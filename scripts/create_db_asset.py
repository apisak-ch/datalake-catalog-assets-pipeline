"""
create_db_asset.py

A generic, config-driven framework for creating (or updating) Database,
Schema, and Table entities in OpenMetadata from a JSON file.

Instead of hardcoding entities in Python, describe them in a JSON config
and run this script against it. To add a new table, database, or schema
later, just edit the JSON and re-run -- no code changes needed.

Usage:
    python scripts/create_db_asset.py configs/scheduler_service_journal_data_extraction/scheduler_hbase_asset_config.json

Idempotency: every entity is created via PUT (createOrUpdate), which
OpenMetadata treats as "create if missing, update in place if it already
exists." That means re-running the same config repeatedly is safe --
nothing gets duplicated, and you can grow the file incrementally over
time (add one new table block, re-run, only that table changes).

NOTE: field names follow OpenMetadata's documented REST schema. If a
call fails with a 4xx error, the response body names the invalid/missing
field -- cross-check against your server's Swagger UI (<host>/swagger-ui
or /docs) if your version differs.
"""

import json
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
    "Content-Type": "application/json",
}


def upsert(collection: str, payload: dict) -> dict:
    """PUT to an OpenMetadata collection endpoint: creates the entity if
    it doesn't exist yet, or updates it in place if it does."""
    url = f"{OPENMETADATA_HOST}/v1/{collection}"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {payload.get('name')}: {resp.text}")
        resp.raise_for_status()
    return resp.json()


def create_database(service: str, db: dict) -> str:
    payload = {"name": db["name"], "service": service}
    if db.get("description"):
        payload["description"] = db["description"]
    upsert("databases", payload)
    print(f"Database: {db['name']}")
    return f"{service}.{db['name']}"


def create_schema(database_fqn: str, schema: dict) -> str:
    payload = {"name": schema["name"], "database": database_fqn}
    if schema.get("description"):
        payload["description"] = schema["description"]
    upsert("databaseSchemas", payload)
    print(f"  Schema: {schema['name']}")
    return f"{database_fqn}.{schema['name']}"


def create_table(schema_fqn: str, table: dict) -> None:
    payload = {
        "name": table["name"],
        "databaseSchema": schema_fqn,
        "columns": table["columns"],
    }
    if table.get("description"):
        payload["description"] = table["description"]
    upsert("tables", payload)
    print(f"    Table: {table['name']} ({len(table['columns'])} columns)")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    service = config["service"]

    for db in config["databases"]:
        db_fqn = create_database(service, db)
        for schema in db.get("schemas", []):
            schema_fqn = create_schema(db_fqn, schema)
            for table in schema.get("tables", []):
                create_table(schema_fqn, table)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_db_asset.py configs/scheduler_service_journal_data_extraction/scheduler_hbase_asset_config.json")
        sys.exit(1)
    main(sys.argv[1])

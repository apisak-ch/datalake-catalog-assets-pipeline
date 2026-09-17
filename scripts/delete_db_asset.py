"""
delete_db_asset.py

Deletes Table entities -- the counterpart to create_db_asset.py. Reads
the exact same assets_config.json format (service/databases/schemas/
tables), but only deletes the TABLES listed -- it deliberately does
NOT delete the parent database/schema, since those are structural and
likely shared with other tables not in this config.

Usage:
    python scripts/delete_db_asset.py configs/<project>/<project>_hbase_asset_config.json

Safety default: soft delete (hardDelete: false) unless a table entry
explicitly sets "hardDelete": true.
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


def delete_table(fqn: str, hard_delete: bool) -> None:
    get_url = f"{OPENMETADATA_HOST}/v1/tables/name/{quote(fqn, safe='')}"
    resp = requests.get(get_url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code == 404:
        print(f"Skipped (not found): {fqn}")
        return
    if resp.status_code != 200:
        print(f"  FAILED to look up {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    entity_id = resp.json()["id"]
    delete_url = f"{OPENMETADATA_HOST}/v1/tables/{entity_id}"
    resp = requests.delete(
        delete_url,
        headers=HEADERS,
        params={"hardDelete": str(hard_delete).lower()},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  FAILED to delete {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Deleted table: {fqn} (hardDelete={hard_delete})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    service = config["service"]
    for db in config["databases"]:
        for schema in db.get("schemas", []):
            for table in schema.get("tables", []):
                fqn = f"{service}.{db['name']}.{schema['name']}.{table['name']}"
                delete_table(fqn, table.get("hardDelete", False))

    print("\nDone. Parent databases/schemas were left untouched -- delete those "
          "manually if you're sure nothing else depends on them.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_db_asset.py configs/<project>/<project>_hbase_asset_config.json")
        sys.exit(1)
    main(sys.argv[1])

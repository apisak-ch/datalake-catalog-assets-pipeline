"""
delete_db_asset.py

Deletes Table entities, using its own dedicated delete config -- a
flat list of tables to remove, not the nested database/schema/table
hierarchy with full column definitions that create_db_asset.py uses.
Delete only needs enough to identify each table, not describe it.

Deliberately does NOT delete the parent database/schema, since those
are structural and likely shared with other tables not in this config.

Config shape:
    {
      "tables": [
        {"service": "hbase", "database": "prod", "schema": "prod", "name": "schedule-action", "hardDelete": false}
      ]
    }

Usage:
    python scripts/delete_db_asset.py configs/<project>/delete_<project>_hbase_config.json

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


def delete_table(table: dict) -> None:
    fqn = f"{table['service']}.{table['database']}.{table['schema']}.{table['name']}"
    hard_delete = table.get("hardDelete", False)

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

    for table in config["tables"]:
        delete_table(table)

    print("\nDone. Parent databases/schemas were left untouched -- delete those "
          "manually if you're sure nothing else depends on them.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_db_asset.py configs/<project>/delete_<project>_hbase_config.json")
        sys.exit(1)
    main(sys.argv[1])

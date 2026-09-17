"""
delete_pipeline_asset.py

Deletes Pipeline entities, using its own dedicated delete config --
just service + name per pipeline, not the full description/sourceUrl/
scheduleInterval detail that create_pipeline_asset.py's config carries.

Config shape:
    {
      "pipelines": [
        {"service": "airflow", "name": "ndid_data_collection", "hardDelete": false}
      ]
    }

Usage:
    python scripts/delete_pipeline_asset.py configs/<project>/delete_<project>_pipeline_config.json

Safety default: soft delete (hardDelete: false) unless a pipeline entry
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


def delete_pipeline(pipeline: dict) -> None:
    fqn = f"{pipeline['service']}.{pipeline['name']}"
    hard_delete = pipeline.get("hardDelete", False)

    get_url = f"{OPENMETADATA_HOST}/v1/pipelines/name/{quote(fqn, safe='')}"
    resp = requests.get(get_url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code == 404:
        print(f"Skipped (not found): {fqn}")
        return
    if resp.status_code != 200:
        print(f"  FAILED to look up {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    entity_id = resp.json()["id"]
    delete_url = f"{OPENMETADATA_HOST}/v1/pipelines/{entity_id}"
    resp = requests.delete(
        delete_url,
        headers=HEADERS,
        params={"hardDelete": str(hard_delete).lower()},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  FAILED to delete {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Deleted pipeline: {fqn} (hardDelete={hard_delete})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for pipeline in config["pipelines"]:
        delete_pipeline(pipeline)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_pipeline_asset.py configs/<project>/delete_<project>_pipeline_config.json")
        sys.exit(1)
    main(sys.argv[1])

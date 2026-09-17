"""
delete_container_asset.py

Deletes Container entities, using its own dedicated delete config --
each entry gives the full FQN directly, rather than the parentName
chain create_container_asset.py's config uses to build up a tree.
Delete only needs to identify each container, not describe its place
in a hierarchy, so there's no ordering requirement here.

Config shape:
    {
      "containers": [
        {"fqn": "hdfs.prod.cleansed.datalake.ndid_data_collection_cleansed.ndid_customer_journey_cleansed", "hardDelete": false}
      ]
    }

Usage:
    python scripts/delete_container_asset.py configs/<project>/delete_<project>_container_config.json

Safety default: soft delete (hardDelete: false) unless a container
entry explicitly sets "hardDelete": true.

NOTE: if you're deleting a whole subtree (a folder and everything
under it), list the deepest/leaf containers first in the config --
deleting a parent while children still exist may fail depending on
the server's own safeguards.
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


def delete_container(container: dict) -> None:
    fqn = container["fqn"]
    hard_delete = container.get("hardDelete", False)

    get_url = f"{OPENMETADATA_HOST}/v1/containers/name/{quote(fqn, safe='')}"
    resp = requests.get(get_url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code == 404:
        print(f"Skipped (not found): {fqn}")
        return
    if resp.status_code != 200:
        print(f"  FAILED to look up {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    entity_id = resp.json()["id"]
    delete_url = f"{OPENMETADATA_HOST}/v1/containers/{entity_id}"
    resp = requests.delete(
        delete_url,
        headers=HEADERS,
        params={"hardDelete": str(hard_delete).lower()},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  FAILED to delete {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Deleted container: {fqn} (hardDelete={hard_delete})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for container in config["containers"]:
        delete_container(container)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_container_asset.py configs/<project>/delete_<project>_container_config.json")
        sys.exit(1)
    main(sys.argv[1])

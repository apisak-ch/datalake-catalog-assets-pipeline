"""
create_container_asset.py

Config-driven script for creating (or updating) Container entities in
OpenMetadata -- same style as create_db_asset.py, create_pipeline_asset.py, etc.

IMPORTANT: containers must be listed in order -- a container's parent
(via "parentName") must appear EARLIER in the same config file, since
parent IDs are resolved from containers already created in this run
(no extra GET calls needed).

Usage:
    python scripts/create_container_asset.py configs/scheduler_service_journal_data_extraction/scheduler_container_config.json

Idempotency: uses PUT, so re-running is safe -- creates if missing,
updates in place if it already exists.
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


def create_container(container: dict, service: str, created_ids: dict) -> str:
    payload = {
        "name": container["name"],
        "service": service,
    }

    if container.get("parentName"):
        parent_id = created_ids.get(container["parentName"])
        if not parent_id:
            raise ValueError(
                f"Parent '{container['parentName']}' for '{container['name']}' hasn't "
                "been created yet in this run -- check the ordering in the config."
            )
        payload["parent"] = {"id": parent_id, "type": "container"}

    for field in ("displayName", "description", "prefix", "fileFormats", "dataModel"):
        if container.get(field):
            payload[field] = container[field]

    url = f"{OPENMETADATA_HOST}/v1/containers"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {container['name']}: {resp.text}")
        resp.raise_for_status()

    result = resp.json()
    parent_note = f" (parent: {container['parentName']})" if container.get("parentName") else " (root)"
    print(f"Container: {container['name']}{parent_note}")
    return result["id"]


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    service = config["service"]
    created_ids = {}
    for container in config["containers"]:
        cid = create_container(container, service, created_ids)
        created_ids[container["name"]] = cid

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_container_asset.py configs/scheduler_service_journal_data_extraction/scheduler_container_config.json")
        sys.exit(1)
    main(sys.argv[1])

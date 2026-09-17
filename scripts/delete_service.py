"""
delete_service.py

Deletes OpenMetadata services -- the counterpart to create_service.py.
Reads the exact same service_config.json format, resolving each
service's real ID by name, then calling DELETE instead of PUT.

Usage:
    python scripts/delete_service.py configs/shared/service_config.json

Safety defaults: soft delete (hardDelete: false) and non-recursive
(recursive: false) unless a service entry explicitly overrides them.
Non-recursive means a service with existing child assets (databases,
topics, etc.) will fail to delete rather than silently cascading --
set "recursive": true on that entry if you really want everything under
it removed too.
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

KIND_TO_COLLECTION = {
    "database": "databaseServices",
    "messaging": "messagingServices",
    "pipeline": "pipelineServices",
    "storage": "storageServices",
}


def get_collection(kind: str) -> str:
    collection = KIND_TO_COLLECTION.get(kind)
    if not collection:
        raise ValueError(f"Unknown kind '{kind}'. Use one of: {list(KIND_TO_COLLECTION)}")
    return collection


def delete_service(service: dict) -> None:
    kind = service.get("kind", "database")
    collection = get_collection(kind)
    name = service["name"]

    get_url = f"{OPENMETADATA_HOST}/v1/services/{collection}/name/{name}"
    resp = requests.get(get_url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code == 404:
        print(f"Skipped (not found): {name}")
        return
    if resp.status_code != 200:
        print(f"  FAILED to look up {name} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    entity_id = resp.json()["id"]
    recursive = service.get("recursive", False)
    hard_delete = service.get("hardDelete", False)

    delete_url = f"{OPENMETADATA_HOST}/v1/services/{collection}/{entity_id}"
    resp = requests.delete(
        delete_url,
        headers=HEADERS,
        params={"recursive": str(recursive).lower(), "hardDelete": str(hard_delete).lower()},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  FAILED to delete {name} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Deleted service: {name} ({kind}, recursive={recursive}, hardDelete={hard_delete})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for service in config["services"]:
        delete_service(service)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_service.py configs/shared/service_config.json")
        sys.exit(1)
    main(sys.argv[1])

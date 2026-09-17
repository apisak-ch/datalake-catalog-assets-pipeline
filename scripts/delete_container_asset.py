"""
delete_container_asset.py

Deletes Container entities -- the counterpart to create_container_asset.py.
Reads the exact same container_config.json format.

Unlike the create script, order here is handled automatically: this
script first walks the config top-to-bottom to reconstruct each
container's full FQN (following parentName chains, the same way
create_container_asset.py resolves parent IDs), then deletes everything
in REVERSE order -- children before parents. This avoids needing
recursive delete and avoids failures from trying to delete a folder
that still has children.

Usage:
    python scripts/delete_container_asset.py configs/<project>/<project>_container_config.json

Safety default: soft delete (hardDelete: false) unless a container
entry explicitly sets "hardDelete": true.
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


def delete_container(fqn: str, hard_delete: bool) -> None:
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

    service = config["service"]
    containers = config["containers"]

    # Forward pass: reconstruct each container's full FQN by following
    # parentName chains, same logic create_container_asset.py uses to
    # resolve parent IDs.
    fqn_by_name = {}
    for c in containers:
        if c.get("parentName"):
            parent_fqn = fqn_by_name.get(c["parentName"])
            if not parent_fqn:
                raise ValueError(
                    f"Parent '{c['parentName']}' for '{c['name']}' not found earlier "
                    "in the config -- check ordering."
                )
            fqn_by_name[c["name"]] = f"{parent_fqn}.{c['name']}"
        else:
            fqn_by_name[c["name"]] = f"{service}.{c['name']}"

    # Reverse pass: delete children before parents.
    for c in reversed(containers):
        fqn = fqn_by_name[c["name"]]
        delete_container(fqn, c.get("hardDelete", False))

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_container_asset.py configs/<project>/<project>_container_config.json")
        sys.exit(1)
    main(sys.argv[1])

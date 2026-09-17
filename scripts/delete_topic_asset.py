"""
delete_topic_asset.py

Deletes Topic entities, using its own dedicated delete config -- just
service + name per topic, not the full schemaFields/partitions detail
that create_topic_asset.py's config carries.

Config shape:
    {
      "topics": [
        {"service": "kafka", "name": "schedule-journal", "hardDelete": false}
      ]
    }

Usage:
    python scripts/delete_topic_asset.py configs/<project>/delete_<project>_topic_config.json

Safety default: soft delete (hardDelete: false) unless a topic entry
explicitly sets "hardDelete": true.

NOTE: if a topic's name contains literal dots, its FQN needs OpenMetadata's
quoting convention (service."name.with.dots") -- same as connect_lineage.py.
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


def delete_topic(topic: dict) -> None:
    fqn = f"{topic['service']}.{topic['name']}"
    hard_delete = topic.get("hardDelete", False)

    get_url = f"{OPENMETADATA_HOST}/v1/topics/name/{quote(fqn, safe='')}"
    resp = requests.get(get_url, headers=HEADERS, params={"fields": "id"}, timeout=30)
    if resp.status_code == 404:
        print(f"Skipped (not found): {fqn}")
        return
    if resp.status_code != 200:
        print(f"  FAILED to look up {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    entity_id = resp.json()["id"]
    delete_url = f"{OPENMETADATA_HOST}/v1/topics/{entity_id}"
    resp = requests.delete(
        delete_url,
        headers=HEADERS,
        params={"hardDelete": str(hard_delete).lower()},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  FAILED to delete {fqn} ({resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Deleted topic: {fqn} (hardDelete={hard_delete})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for topic in config["topics"]:
        delete_topic(topic)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/delete_topic_asset.py configs/<project>/delete_<project>_topic_config.json")
        sys.exit(1)
    main(sys.argv[1])

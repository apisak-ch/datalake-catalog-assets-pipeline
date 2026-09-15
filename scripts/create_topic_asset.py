"""
create_topic_asset.py

Config-driven script for creating (or updating) Topic entities in
OpenMetadata -- same style as create_pipeline_asset.py, create_db_asset.py, etc.

Usage:
    python scripts/create_topic_asset.py configs/scheduler_service_journal_data_extraction/topic_config.json

Idempotency: uses PUT, so re-running is safe -- creates if missing,
updates in place if it already exists.
"""

import json
import sys

import requests

# --- Configuration: fill these in for your environment ---
OPENMETADATA_HOST = "http://localhost:8585/api"
OPENMETADATA_TOKEN = "your-personal-access-token"
# -----------------------------------------------------------

HEADERS = {
    "Authorization": f"Bearer {OPENMETADATA_TOKEN}",
    "Content-Type": "application/json",
}


def create_topic(topic: dict) -> None:
    payload = {
        "name": topic["name"],
        "service": topic["service"],
        "partitions": topic.get("partitions", 1),
    }
    if topic.get("displayName"):
        payload["displayName"] = topic["displayName"]
    if topic.get("description"):
        payload["description"] = topic["description"]
    if topic.get("schemaFields"):
        payload["messageSchema"] = {
            "schemaType": topic.get("schemaType", "Other"),
            "schemaFields": topic["schemaFields"],
        }

    url = f"{OPENMETADATA_HOST}/v1/topics"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {topic['service']}.{topic['name']}: {resp.text}")
        resp.raise_for_status()

    print(f"Topic: {topic['service']}.{topic['name']} ({len(topic.get('schemaFields', []))} fields)")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for topic in config["messaging"]:
        create_topic(topic)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_topic_asset.py configs/scheduler_service_journal_data_extraction/topic_config.json")
        sys.exit(1)
    main(sys.argv[1])

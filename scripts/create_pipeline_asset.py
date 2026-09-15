"""
create_pipeline_asset.py

Config-driven script for creating (or updating) Pipeline entities in
OpenMetadata -- same style as create_db_asset.py, connect_lineage.py, and
create_service.py.

Usage:
    python scripts/create_pipeline_asset.py configs/scheduler_service_journal_data_extraction/scheduler_pipeline_config.json

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

# Optional fields that get passed through as-is if present in the config.
OPTIONAL_FIELDS = ("displayName", "description", "sourceUrl", "scheduleInterval", "tasks")


def create_pipeline(pipeline: dict) -> None:
    payload = {
        "name": pipeline["name"],
        "service": pipeline["service"],
    }
    for field in OPTIONAL_FIELDS:
        if pipeline.get(field):
            payload[field] = pipeline[field]

    url = f"{OPENMETADATA_HOST}/v1/pipelines"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {pipeline['service']}.{pipeline['name']}: {resp.text}")
        resp.raise_for_status()

    print(f"Pipeline: {pipeline['service']}.{pipeline['name']}")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for pipeline in config["pipelines"]:
        create_pipeline(pipeline)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_pipeline_asset.py configs/scheduler_service_journal_data_extraction/scheduler_pipeline_config.json")
        sys.exit(1)
    main(sys.argv[1])

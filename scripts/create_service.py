"""
create_service.py

Config-driven script for creating (or updating) OpenMetadata services --
Database, Messaging, Pipeline, or Storage -- in the same style as
create_db_asset.py and connect_lineage.py.

Run this once before pointing create_db_asset.py (databases), or the
topic/pipeline/container equivalents, at a new service name. For services
you're populating manually via API (no live connector), each kind has a
"Custom" serviceType -- this is also what "manual-pilot" and
"hbase-service" use.

Usage:
    python scripts/create_service.py configs/shared/service_config.json

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

# Maps the "kind" you write in the config to its REST collection and the
# default "Custom" serviceType for manual (no live connector) services.
KIND_TO_CONFIG = {
    "database": {"collection": "databaseServices", "default_type": "CustomDatabase"},
    "messaging": {"collection": "messagingServices", "default_type": "CustomMessaging"},
    "pipeline": {"collection": "pipelineServices", "default_type": "CustomPipeline"},
    "storage": {"collection": "storageServices", "default_type": "CustomStorage"},
}


def create_service(service: dict) -> None:
    kind = service.get("kind", "database")
    kind_conf = KIND_TO_CONFIG.get(kind)
    if not kind_conf:
        raise ValueError(f"Unknown kind '{kind}'. Use one of: {list(KIND_TO_CONFIG)}")

    service_type = service.get("serviceType", kind_conf["default_type"])

    payload = {
        "name": service["name"],
        "serviceType": service_type,
        "connection": {
            "config": {
                "type": service_type,
                # Only meaningful if you later run a real ingestion workflow
                # against this service. Harmless placeholder otherwise.
                "sourcePythonClass": service.get("sourcePythonClass", "manual.CustomSource"),
            }
        },
    }
    if service.get("description"):
        payload["description"] = service["description"]

    url = f"{OPENMETADATA_HOST}/v1/services/{kind_conf['collection']}"
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  FAILED ({resp.status_code}): {service['name']}: {resp.text}")
        resp.raise_for_status()

    print(f"Service: {service['name']} ({kind}, {service_type})")


def main(config_file: str) -> None:
    with open(config_file) as f:
        config = json.load(f)

    for service in config["services"]:
        create_service(service)

    print("\nDone.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_service.py configs/shared/service_config.json")
        sys.exit(1)
    main(sys.argv[1])

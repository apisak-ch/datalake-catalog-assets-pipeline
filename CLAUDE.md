# datalake-catalog-assets-pipeline — Project Conventions

This project maintains OpenMetadata's data catalog via config-driven Python
scripts (not manual UI entry, not live ingestion connectors). Every entity
is created/updated by writing a JSON config and running the matching
`create_*.py` script.

## Services (current inventory)

| Service | Kind | Type | Notes |
|---|---|---|---|
| `kafka` | messaging | CustomMessaging | topics: schedule-journal, customer-service-journal |
| `hbase` | database | CustomDatabase | manual, no live connector |
| `k8s-application` | pipeline | CustomPipeline | online/streaming consumer apps |
| `airflow` | pipeline | CustomPipeline | batch DAGs |
| `hdfs` | storage | CustomStorage | file zones |
| `hive` | database | CustomDatabase | manual, no live connector (see naming below) |

All services here are **manual** (no live ingestion connector attached).
If a live connector is ever added for any of them, its auto-created
Database-level name may not match what we've built manually — check before
assuming they'll merge cleanly.

## Naming conventions

- Service `name`: lowercase-hyphenated, no `-service` suffix (e.g. `hbase`,
  not `hbase-service`). `name` is **immutable** once created — get it right
  before creating, since fixing it later means deleting and recreating.
- Environment is always `prod` (not `uat`/`default`) in database/namespace
  names, even when the source sample data came from `uat`. Source docs
  often express this as a bracket placeholder — `[env]`, `[namespace]`,
  etc. — replace any such placeholder with `prod` directly, without
  asking each time.
- **Manual/custom services** (no live connector): Database = real system
  name, Schema = `default`. Example: `hbase.prod.prod.<table>`.
- **Native connectors** (e.g. a real Hive connector): Database = `default`
  (or a chosen fixed name), Schema = real system db name. This is the
  **opposite** structural shape from the manual convention above — don't
  mix them up.
- Kafka topic/entity names must match the **real** system identifier, not
  a descriptive label from a diagram or doc. Diagram labels have
  repeatedly turned out to differ from real names in this project (DAG
  names, k8s app names, topic names) — always verify.
- If a name contains literal dots (e.g. a topic named
  `scheduler.scheduler.foo`), its FQN needs OpenMetadata's quoting
  convention: `service."name.with.dots"`, URL-encoded when used in API
  calls.

## HBase modeling

- Model as nested STRUCT, not flat columns:
  `rowkey -> {row-shape} -> {family} -> qualifier -> [fields]`
- A row key can have multiple shapes (e.g. an hour-bucket index row vs. a
  per-record detail row) — model each shape as its own child under
  `rowkey`, each carrying only the column family that applies to it.
- Dynamic/unbounded qualifier key space (new keys keep appearing, no fixed
  vocabulary) → `MAP<string,string>`.
- Fixed/known field vocabulary (even if the *raw* qualifier string is
  compound/unique per record) → `STRUCT` with named children for the
  known business fields.
- Use `displayName` for `{bracket}`-style pattern notation (e.g.
  `{cif}_{seqID}`); keep the real `name` FQN-safe — no braces, since they
  cause URL/FQN friction (see Naming conventions).

## Type mapping

- Money/amount fields → `DECIMAL` with `dataTypeDisplay: "decimal(18,2)"`.
- Hive external tables: match the **real DDL exactly**, even if it's
  all-STRING (common for loosely-typed CSV-backed external tables). Don't
  "improve" the types — accuracy to the real system beats semantic
  precision.
- Topic schemas use a smaller type enum than tables — no `DECIMAL`, no
  `TEXT`. Map `Numeric` → `DOUBLE`, `Text` → `STRING`.

## Workflow rules

- **Config files are scoped to current/active work only**, not cumulative.
  Remove already-created entries before adding new ones. This is purely a
  config-file convention — removing an entry from the JSON does **not**
  delete the entity from OpenMetadata (scripts are PUT/create-or-update
  only, except `delete_lineage.py`).
- **Draft before you push.** Never run a `create_*.py` script against
  OpenMetadata without showing the person the draft config first. Real
  source docs in this project have repeatedly contained ambiguities,
  wrong table names, and ambiguous/wrapped terminal output that only
  got caught through review — don't assume a source doc is unambiguous.
- Flag ambiguity in a source document explicitly rather than silently
  guessing a resolution.
- When a config's data doesn't match what its filename/label claims
  (e.g. a "schedule-setting" paste that's actually schedule-action data),
  say so and confirm before proceeding.

## Scripts in this project

Scripts live in `scripts/`. Configs live in `configs/<project>/`, where
`<project>` is the full, unambiguous project name matching its real DAG
name (`scheduler_service_journal_data_extraction`, `ndid_data_collection`)
— not an abbreviation. Filenames inside each folder keep a **short**
project prefix (`scheduler_`, `ndid_`) rather than the full folder name
or no prefix at all — short enough to stay readable, but still
identifiable at a glance in an editor tab where the folder path isn't
visible. `configs/shared/` holds `service_config.json` only (no prefix),
since services aren't owned by any single project.

Run everything from the repo root, e.g.:

```bash
python scripts/create_db_asset.py configs/scheduler_service_journal_data_extraction/scheduler_hbase_asset_config.json
```

**One-time setup per person:** `pip install -r requirements.txt`, then
`cp .env.example .env` and fill in your real `OPENMETADATA_HOST` /
`OPENMETADATA_TOKEN`. Scripts read credentials from `.env` (via
`python-dotenv`), never hardcoded — `.env` is gitignored, only
`.env.example` (a template with no real values) is committed. Missing
`.env` fails loudly with a `KeyError` naming the missing variable,
rather than silently defaulting to something wrong.

| Script | Example config | Creates |
|---|---|---|
| `scripts/create_service.py` | `configs/shared/service_config.json` | Services (any kind) |
| `scripts/create_db_asset.py` | `configs/<project>/<project>_hbase_asset_config.json`, `..._hive_asset_config.json` | Databases, schemas, tables |
| `scripts/create_topic_asset.py` | `configs/<project>/<project>_topic_config.json` | Topics |
| `scripts/create_pipeline_asset.py` | `configs/<project>/<project>_pipeline_config.json` | Pipelines |
| `scripts/create_container_asset.py` | `configs/<project>/<project>_container_config.json` (or `_ftp_container_config.json` / `_hdfs_container_config.json` when a project spans multiple storage services) | Containers (order matters — parent before child) |
| `scripts/connect_lineage.py` | `configs/<project>/<project>_lineage_config.json` | Lineage edges, with optional `pipeline` attribution |
| `scripts/disconnect_lineage.py` | `configs/<project>/<project>_lineage_config.json` | Removes lineage edges (the one delete-capable script) |

Current projects: `configs/scheduler_service_journal_data_extraction/`
(6 files, `scheduler_` prefix) and `configs/ndid_data_collection/`
(5 files, `ndid_` prefix — no `topic_config` since this pipeline has no
Kafka involvement).

All scripts read `OPENMETADATA_HOST` / `OPENMETADATA_TOKEN` from constants
at the top of the file — set these before running anything.

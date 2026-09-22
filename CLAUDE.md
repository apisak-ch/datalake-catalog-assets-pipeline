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
| `ftp-mymo` | storage | CustomStorage | inbound: MyMo-dedicated source FTP (`/data/prod/file/mymo/ToLAKE/`) |
| `ftp-k8s` | storage | CustomStorage | outbound: delivery to downstream k8s processors (`/delta/datasource/`) |

Separate FTP servers get separate services, since the service is the only
place host/connection info has a structured home — merging two hosts into
one service makes it impossible to tell which machine a file lives on.
Merge only when two IPs are the *same* logical system (DR pair,
load-balanced cluster), where an address change shouldn't churn FQNs.

All services here are **manual** (no live ingestion connector attached).
If a live connector is ever added for any of them, its auto-created
Database-level name may not match what we've built manually — check before
assuming they'll merge cleanly.

## Naming conventions

- Service `name`: lowercase-hyphenated, no `-service` suffix (e.g. `hbase`,
  not `hbase-service`). `name` is **immutable** once created — get it right
  before creating, since fixing it later means deleting and recreating.
  **Renaming a service is an admin-only operation.** It is not a rename at
  all: it deletes the service and every entity under it, across *all*
  projects that use it, then rebuilds them. If you think a service name is
  wrong, raise it with the catalog admin rather than doing it yourself —
  don't add a `delete_service.py` entry for a rename. See "Renaming a
  service" below for the procedure the admin follows.
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
  only, except the `delete_*.py` / `disconnect_lineage.py` scripts).
- **Draft before you push.** Never run a `create_*.py` script against
  OpenMetadata without showing the person the draft config first. Real
  source docs in this project have repeatedly contained ambiguities,
  wrong table names, and ambiguous/wrapped terminal output that only
  got caught through review — don't assume a source doc is unambiguous.
- **Always summarize before deleting.** Before running any `delete_*.py`
  script or `disconnect_lineage.py`, list exactly what will be removed
  (entity names/FQNs, and whether `hardDelete`/`recursive` is set) and
  get confirmation first. This applies every time, not just the first
  time in a conversation — deletes are harder to undo than creates, and
  a config can silently include more than the person had in mind.
- Flag ambiguity in a source document explicitly rather than silently
  guessing a resolution.
- When a config's data doesn't match what its filename/label claims
  (e.g. a "schedule-setting" paste that's actually schedule-action data),
  say so and confirm before proceeding.
- **Every table or file-based asset needs a real schema — a table, or a
  file/container at any zone (raw, cleansed, gold_safe, or equivalent),
  on HDFS, FTP, or any storage service.** Don't create one as a
  schema-less shell without saying so out loud. If the source material
  doesn't give real column-level detail for something in scope, stop and
  tell the person exactly what's missing (which table/file, which zone)
  rather than quietly drafting it without columns or silently inferring
  one from a sibling zone. It's fine to proceed with everything that
  *does* have real schema while flagging the gap for what doesn't — but
  the gap itself must be said, not left implicit in a shell entity.
- **Check upstream existence before assuming it, not before every
  create.** `create_*.py` scripts PUT (create-or-update), so re-running
  against an entity your own config creates is always safe — no need to
  check first. Checking matters specifically for entities a config only
  *references* without creating: a lineage edge's `fromEntity`/
  `toEntity` pointing at another project's table/container, or any
  source-doc claim that something "already exists" elsewhere. Verify
  those with `scripts/check_entity.py <type> <fqn>` (read-only GET, no
  side effects) before drafting the reference — `connect_lineage.py`
  fails at runtime if the endpoint doesn't exist, and this project has
  already had a doc's input table turn out to not be cataloged at all
  (`mymo_register_data_extraction`'s `register`/`deactivation` inputs).

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
| `scripts/check_entity.py` | none (CLI args: `<type> <fqn> [<fqn> ...]`) | Nothing — read-only existence check, see Workflow rules |

Current projects: `configs/scheduler_service_journal_data_extraction/`
(6 files, `scheduler_` prefix) and `configs/ndid_data_collection/`
(5 files, `ndid_` prefix — no `topic_config` since this pipeline has no
Kafka involvement).

## Deleting assets

Each `create_*.py` script has a `delete_*.py` counterpart (plus
`disconnect_lineage.py` for lineage), but **delete scripts use their
own dedicated config format, not the create config** — delete only
needs enough to identify an entity, not fully describe it (no columns,
no descriptions, no nested hierarchy).

| Script | Example config | Config shape |
|---|---|---|
| `scripts/delete_service.py` | `configs/shared/delete_service_config.json` | `{"services": [{"kind", "name", "recursive"?, "hardDelete"?}]}` |
| `scripts/delete_db_asset.py` | `configs/<project>/delete_<project>_hbase_config.json` | `{"tables": [{"service", "database", "schema", "name", "hardDelete"?}]}` — flat list, doesn't touch the parent database/schema |
| `scripts/delete_topic_asset.py` | `configs/<project>/delete_<project>_topic_config.json` | `{"topics": [{"service", "name", "hardDelete"?}]}` |
| `scripts/delete_pipeline_asset.py` | `configs/<project>/delete_<project>_pipeline_config.json` | `{"pipelines": [{"service", "name", "hardDelete"?}]}` |
| `scripts/delete_container_asset.py` | `configs/<project>/delete_<project>_container_config.json` (split per service if the project spans more than one, e.g. `delete_<project>_ftp_container_config.json` / `delete_<project>_hdfs_container_config.json` — same split as the create configs) | `{"containers": [{"fqn", "hardDelete"?}]}` — full FQN given directly, no parent-chain resolution needed |
| `scripts/disconnect_lineage.py` | `configs/<project>/<project>_lineage_config.json` (same shape as `connect_lineage.py` — lineage is the one exception, since an edge is already just two FQNs) | Removes lineage edges |

Defaults are deliberately conservative: soft delete (`hardDelete: false`)
unless an entry sets `"hardDelete": true`, and `delete_service.py`
defaults to non-recursive (`recursive: false`) so a service with
existing children fails to delete rather than silently cascading.

**Delete configs must mirror create's file-splitting boundaries, even
though the content shape differs.** If a project's containers span
multiple services (e.g. `ndid_data_collection` has both `ftp-mymo` and
`hdfs`), that's two separate `create_*_container_config.json` files —
so its delete configs must also be two separate files
(`delete_ndid_ftp_container_config.json`,
`delete_ndid_hdfs_container_config.json`), never one combined file
covering both services. The dedicated-delete-config change (flat lists,
FQNs instead of nested hierarchy) is about *what's inside* each file,
not license to merge files that create keeps separate.

**Always summarize what will be deleted and get confirmation before
running any `delete_*.py` script or `disconnect_lineage.py`** — see
Workflow rules above. This applies every time, not just once per
conversation.

## Renaming a service (admin only)

**Not a team operation** — see Naming conventions. Service names are
immutable, so a "rename" is really create-new → copy-everything →
delete-old, and it cascades across every project using that service.
Raise the name with the admin instead of doing this yourself.

The ordering matters: every step is additive until the last one, so the
old service keeps serving lineage the whole time and a mistake anywhere
in 3–6 means you just stop, with nothing broken.

1. **Survey the blast radius.** Query the live API for every container/
   table under the service, the lineage edges touching them, and — the
   decisive one — whether any carry owners/tags/followers added by hand
   in the UI. Configs only reproduce what's in the JSON, so UI-added
   metadata is destroyed by the rebuild. If any exists, stop: it has to
   be captured or re-applied by hand afterwards.
2. **Swap the name in the configs.** `"service": "<old>"` in the
   container/asset configs, `"<old>.` → `"<new>.` in the lineage and
   delete configs. Match on the trailing quote/dot so sibling services
   sharing a prefix (`ftp` vs `ftp-k8s`) can't be hit by accident, then
   review every changed line in `git diff`.
3. **Create the new service** (`create_service.py`). Both now coexist.
4. **Rebuild the children** — re-run the same container/asset configs,
   now pointing at the new service.
5. **Rebuild the lineage** — re-run the lineage configs.
6. **Verify parity before destroying anything** — compare old vs new
   entity-by-entity: same paths, same column counts, same edge count.
7. **Delete the old service.** Needs `recursive: true` (it has
   children); prefer `hardDelete: false` — the old name stays occupied,
   which doesn't matter since you're not reusing it. Summarize and
   confirm first, as with any delete.

This only works because the container/asset configs still hold their
full contents. It's the one case where the "scoped to active work only"
trimming rule in Workflow rules would have cost real work — trimmed
configs mean nothing to re-run at steps 4–5, and every schema has to be
reconstructed from the API or the source docs by hand.

All scripts read `OPENMETADATA_HOST` / `OPENMETADATA_TOKEN` from constants
at the top of the file — set these before running anything.

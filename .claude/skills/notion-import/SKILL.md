---
name: notion-import
description: Use when the person wants to import, convert, or extract asset/pipeline information from Notion into an OpenMetadata config file — whether from a live Notion connector/MCP or an exported Markdown file. Triggers on requests like "pull this Notion page into a config", "import this pipeline doc from Notion", "fetch [page name/link] and turn it into a config", or when a .md file that looks like a Notion export is present alongside a request to catalog it.
---

# Notion → OpenMetadata Config

Converts a Notion pipeline/requirements doc into a draft OpenMetadata
config, matching the JSON shapes already used in this project (see
CLAUDE.md for the full convention reference). Produces a **draft only**
— never runs a `create_*.py` script as part of this skill.

Two ways to get the source content — use whichever the person has set
up. Everything from step 2 onward is identical either way.

## Getting the content

**A. Live connector (preferred when available).** If a Notion MCP
connector is connected, fetch the page directly (by URL, page name, or
search) rather than asking for an export. This removes the
subpage-vs-shared-registry problem export-based work used to hit:
**any** linked Notion page is directly fetchable regardless of where it
sits in the workspace hierarchy, so just follow links that look
relevant (schema/spec pages, per-file detail pages) instead of stopping
at an unresolved link.

Don't chase every link indiscriminately, though — fetch the main doc,
then fetch links that plausibly hold what's still missing (a schema, a
spec, a linked detail page for something the main doc only names). Stop
once you have enough to draft the entities in scope, or once you've hit
a small number of genuinely relevant fetches without new information —
don't wander the whole workspace. If something still isn't resolvable
after a reasonable attempt, that's what step 7's gap list is for.

**B. Exported Markdown file (fallback).** Look for the `.md` file the
person means (and any sibling folder of the same name, holding
sub-pages/attachments). Read it directly.

If the doc contains links formatted as full `app.notion.com` URLs (not
relative paths) to pages that look like they'd hold needed detail,
**before treating the doc as incomplete, ask the person to re-export
with Notion's "Include subpages" toggle turned on.** This bundles
genuine parent→child pages but will **not** bundle links to pages that
live elsewhere in the workspace as a shared/reused registry. If
subpages were already included and a link still resolves to nothing,
that's the shared-registry case — go to step 7's gap list rather than
re-asking for the same re-export, or suggest switching to path A if a
connector is available, since it doesn't have this limitation at all.

## Procedure

2. **Classify the content before extracting anything:**
   - **Structured** (real tables with consistent columns like
     Name / Type / Description) — proceed with confidence, this maps
     cleanly onto our config schemas.
   - **Freeform** (prose, headers, no tabular structure) — proceed, but
     flag every inference as an assumption rather than a fact. Don't
     silently resolve ambiguity the way a strict template would remove it.

3. **Identify what kind of asset(s) the doc describes** — a service? A
   database/table/topic? A pipeline? Lineage between existing entities? A
   single doc may describe several of these at once (e.g. a full
   pipeline spec covering a topic, a table, and a pipeline entity). Match
   each piece to the config shape in CLAUDE.md's script table.

   Distinguish **schema/architecture docs** (paths, DAG names, table
   names, column lists — the thing you're actually cataloging) from
   **business-context docs** (activity codes, status value meanings,
   application state transitions — describe what the *data means*, not
   its structure). Both are useful, but don't treat a business-context
   doc as a source of column names/types just because it mentions
   field-like terms (e.g. `ndid_status`, `application_state`) — use it to
   enrich descriptions, not to invent a schema.

   If both an overview doc (e.g. a top-level mermaid diagram) and a more
   detailed sub-page on the same pipeline exist, **the detailed page
   wins where they differ** — overview diagrams in this project have
   repeatedly turned out to be simplified (missing zones, missing
   validation steps, non-literal process names).

   Pipeline pages in this project typically carry a **"Related Data"**
   table linking out to per-file/per-table detail pages (e.g. "FTP -
   `<name>`", "HDFS - `<name>`", "`<schema>.<table>`"). **For file and
   container (data) configs, source schema and path facts only from
   those linked detail pages — not from the context diagram or other
   sections (Requirements, sheet-spec links).** Treat the context
   diagram as illustrative of pipeline flow only; if a zone (e.g. a
   staging copy before a Hive load) appears in an existing catalog
   config but has no corresponding Related Data entry, that's an
   inference from project convention, not something sourced from this
   doc — flag it as such in step 7.

   **Default preference: create HDFS/file/Hive assets that match
   Related Data one-for-one — don't add an extra zone or entity just
   because a sibling pipeline's convention has one.** An earlier
   pipeline in this project (`open_account_data_collection`) got a
   `gold_safe` staging zone pushed to OpenMetadata even though nothing
   in its Related Data table backed it — the person confirmed that was
   fine to leave as-is since that project was a POC, not that it should
   happen again. Before creating (not just drafting) any entity that
   exists only because of cross-project convention, name it as
   convention-only and get an explicit yes — don't fold it into the
   normal "ask which script to run" confirmation as if it were sourced.

   Check the doc's own internal consistency, not just against other
   docs — a doc can contradict itself (e.g. a table named one way in its
   header and a different way three sections later). Flag it rather than
   picking one silently, the same as any other ambiguity.

4. **Apply the project's standing conventions** (from CLAUDE.md) —
   naming, manual-vs-native Database/Schema shape, HBase nested modeling,
   type mapping. Don't re-derive these from scratch; they're already
   established. If this pipeline follows an established pattern from a
   prior pipeline in this project (e.g. loader tables excluded from the
   catalog, a specific safe/unsafe split shape), ask whether the same
   convention applies here rather than assuming it automatically carries
   over — conventions have been per-pipeline choices as often as they've
   been project-wide rules.

5. **Cross-check against existing configs/entities where possible.** If
   the doc references a table/topic/service that should already exist in
   this project, check the current config files for it rather than
   assuming the doc is the sole source of truth — this project has
   repeatedly found mismatches between docs and reality (wrong table
   names, renamed services, outdated diagram labels).

6. **Write the draft config** to a new or existing `*_config.json` file,
   following the exact JSON shape the matching script expects.
   **Whether HDFS raw and cleansed zones share an identical schema
   varies by pipeline** — some genuinely transform between zones, some
   don't. Don't assume either way across pipelines; check each zone's
   *own* linked detail page. What must never happen: a zone's detail
   page gives a real column-level schema and it gets dropped from the
   config anyway (e.g. because it looked like a duplicate of a sibling
   zone's schema) — carry over whatever schema each zone's own source
   page actually states, even if it happens to match another zone's.
   Only treat one zone's schema as standing in for another's (e.g. a
   `gold_safe` staging copy described as "same content as the cleansed
   zone" with no schema page of its own) when that zone has **no
   detail page at all** — and say so explicitly per step 7, since that's
   an inference, not a sourced fact. Every
   table or file/container in scope needs a **real schema** — if the doc
   doesn't give real column-level detail for one of them (e.g. real
   DAG/pipeline structure exists but a specific file's columns don't),
   that's not a quiet gap to leave implicit in a schema-less shell — it
   must be called out explicitly in step 7, by name, every time. Don't
   fill it with invented columns, and don't silently borrow another
   zone/file's schema for it without saying that's what happened.

7. **Stop. Do not run the create/delete script.** Present the draft and:
   - List every field or structural choice that was **inferred rather
     than stated explicitly** in the source doc (e.g. "no data type was
     given for `X`, inferred STRING from the example value").
   - List anything **genuinely ambiguous** that needs a human decision
     rather than a best-effort guess (e.g. conflicting information,
     missing required fields, a name that doesn't match an existing
     entity).
   - **Name every table or file/container that's missing a real
     schema**, one by one — don't let this blend into the general
     ambiguity list. If three files were drafted and one has no schema,
     say clearly which one and why (link unresolved, page fetchable but
     empty, whatever the actual reason is).
   - If the content doesn't support a full draft (common for an
     overview/index page that only links out to real detail elsewhere,
     or a linked page that couldn't be fetched/found), produce a
     **gap list** instead of forcing a thin draft: which specific pages
     or files are still needed, and what they should contain.
   - Ask which script to run and confirm before running it.

## What this skill does not do

- Does not push anything to OpenMetadata directly — always stops at the
  draft-and-review step, regardless of which content source was used.
- Does not chase links indefinitely when using a live connector — fetch
  what's plausibly relevant, then stop and use the gap list for anything
  still missing rather than exhaustively crawling the workspace.
- Does not invent structure a freeform doc doesn't have. If content is
  too unstructured to extract reliably, say so plainly rather than
  forcing a low-confidence extraction.

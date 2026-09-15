# datalake-catalog-assets-pipeline

## What is this?

We catalog our data — Kafka topics, HBase/Hive tables, HDFS/FTP files,
and how they connect ("lineage") — in **OpenMetadata**. Instead of
clicking through the OpenMetadata website by hand, we describe things
in simple text files (JSON) and run scripts that do it for us.

You don't need to know Python. Claude writes and runs the scripts —
you just answer questions about the data.

---

## One-time setup

1. **Get the folder.** Clone/download this repo.
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up access:** Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   Then fill in the real `OPENMETADATA_HOST` and `OPENMETADATA_TOKEN`
   (ask a teammate if you don't have these). `.env` stays private to
   you — never shared.
4. **Connect Notion:** Claude Desktop → Settings →
   Connectors → Add Connector → `https://mcp.notion.com/mcp` → log in.
   Doesn't work inside a Code session? Just export the Notion page and
   hand Claude the file instead.
5. **Open the folder in Claude Desktop's Code tab.** It reads
   `CLAUDE.md` automatically — our conventions, no need to re-explain.

Done. Just once.

---

## Adding a new pipeline

1. **Give Claude the docs** — Notion page, export, screenshots,
   whatever you have.
2. **Claude checks what already exists** — new service needed, or just
   new entries under something we already track?
3. **Claude drafts the config files** — nothing sent to OpenMetadata
   yet, just a draft.
4. **You review it** — Claude flags guesses and anything genuinely
   unclear (e.g. "is this table `X` or `Y`?"). Check this before
   moving on.
5. **Claude runs the scripts** — creates everything in OpenMetadata.
6. **Claude draws the lineage** — how the data flows, same
   draft-then-review process.
7. **Check it in OpenMetadata** — your new tables and their lineage
   should be there.

---

## FAQ

**Need to know Python?** No.

**What if something's wrong?** Nothing's created until you approve the
draft in step 4. Already created something by mistake? Ask Claude —
`disconnect_lineage.py` removes lineage edges; entities can be deleted
from the OpenMetadata website.

**Where do the naming rules live?** `CLAUDE.md` — Claude reads it
automatically every session.

**Stuck?** Just describe what you're seeing to Claude.
# AGENTS.md — deData-PPC-Analysis (Peet Limited, ASX:PPC)

## What this repo is
Weekly sales-velocity analysis on top of `deData-PPC-MasterplanDownloader`
snapshots. **No ETL, no database, no website wiring** — snapshot diffs in,
Markdown pack + charts out.

## Repo boundary (hard rule)
- `deData-PPC-MasterplanDownloader` is the **snapshotter: read-only from here**.
  Never create, edit, or move files in that checkout from this project. It stays clean.
- **All work lives here**: `scripts/`, `reports/`, `charts/`, `_peet/` scratch.
- If the downloader needs a change (e.g. the spring-mountain spec below), write
  the spec here and apply it there only on explicit instruction.

## Data flow
1. Downloader (Cloud Run Job `ppc-masterplan-job`, weekly) GETs every Peet
   community page and snapshots the embedded
   `var lotConfig = {lots_data, all_lots_with_status, mapConfig}` to
   `ppc/masterplans/{json,csv}/` in GCS bucket `masterplans` (gzipped).
2. **`python3 scripts/sync.py`** lists `gs://masterplans/ppc/masterplans/json/`,
   groups objects into runs by timestamp, keeps runs with ≥20 estates, pulls the
   newest `--latest N` (default 2) into `./_in` and **gunzips** them.
   Needs `gcloud auth login` (read-only; never writes to the bucket).
   `--dry-run` previews, `--include-csv` also fetches the flattened CSVs.
3. `python3 scripts/weekly.py --input ./_in` diffs the two latest **full** runs
   (≥20 estates) lot-by-lot on `(community, lot_id)` → `reports/<date>/`,
   `charts/<date>_net_sales.png`, appends `reports/history.csv`.
   `weekly.py` reads `*.json` **and** `*.json.gz`, so it also works on a raw
   bucket copy without the sync step.
4. `_peet/` holds one-off research crawls (raw HTML, `live/*.json`,
   `lots_all.csv`). Scratch — never an input to `weekly.py`.

**Why sync is code and not a README command:** the bucket stores
`{ts}-ppc-website-masterplan-data-{slug}.json.gz`. A plain
`gcloud storage cp -r … ./_in` leaves the `.gz` suffix, and the original
`weekly.py` globbed only `*.json` — so a "successful" sync produced a directory
that made the analysis exit with `need 2 full runs`. Both halves are fixed:
`sync.py` decompresses, `weekly.py` accepts either form.

## Lot masterdata source
Peet serves lot masterdata **first-party**: their WordPress backend
(`peet` theme, multisite) embeds the full inventory server-side in each
community page. No third-party lot-data service on the page. Evidence points to
Microsoft Dynamics 365/Dataverse upstream (`product_id` GUIDs + ClickDimensions
analytics) — inference, not confirmed.

### What is published per lot (verified 2026-11-06)
Crawled all 36 discovered community URLs: 34 return a `lotConfig`, **6,779 lots**.

- **Every lot** carries exactly 6 fields: `lot_id, lot_status, lot_number,
  lot_name, stage_name, lot_post_status`.
- **Published lots only** (`lot_post_status: publish`) add price and specs:
  `price, size, frontage, bedrooms, bathrooms, garage_spaces, product_type,
  product_id, stories, open_hours` (also in `lots_data`).
- Live split: 3,869 status 7 (sold, 57%) · 1,159 status 4 · 774 status 1 ·
  492 status 5 · 434 status 2 · 33 status 8 · 13 status 3.
- **221 lots site-wide are `publish`** — i.e. ~3% of inventory. Of the 434
  status-2 lots, half are `draft` (available but not advertised).
- **No sold lot carries a price.** Sale price, contract date, settlement date
  and buyer are never published; sold lots keep 6 fields and drop out of
  `lots_data`. "Sale" is a state flag, so events are only derivable by
  snapshot diffing (status → 7, or delisting) — dated to the pull, priced at
  last-ask.
- REST adds nothing: `/wp-json/wp/v2/lots` and `/crm-syndication/v1/lots*`
  expose **6 syndicated lots** total; `crm-syndication/v1/network-sites` is 401;
  `peet-geojson/v1/datasets` returns `[]`; `mapConfig` carries only a boundary
  ring (and only on 8 estates — 5–23 points each).

## Estate masterplans — dated, curated versions
Peet publishes each estate's lot-selection map as a **vector SVG on the
`/for-sale/` page**, not on the marketing page:

```
https://www.peet.com.au/{state}/{slug}/wp-content/uploads/…/{Slug}_MP_{DDMMYY}.svg
```

These are layered maps (`Base`, `POS`, `HATCH`) with every lot drawn as a path
and numbered — the closest thing Peet exposes to lot geometry.

**Versioning.** The `_MP_DDMMYY` suffix is the map's own date. Store one file
per estate per version: `_peet/masterplans/<estate>/<YYYY-MM-DD>.png`, indexed in
`_peet/masterplans/index.csv` (`estate, version_date, map_kind`). A re-run that
finds a later `_MP_` date adds a sibling file rather than overwriting. Where
there is no SVG, the date comes from the PDF/image filename, else the upload
folder (`uploads/…/YYYY/MM/`) as `YYYY-MM-01`.

**Rendering — use headless Chrome, not PyMuPDF.** The SVGs carry their fills in
CSS classes; PyMuPDF renders them as black silhouettes. Chrome
(`--headless=new --screenshot --window-size=<viewBox aspect>`) colours them
correctly. Chrome needs `--user-data-dir` inside the sandbox.

**Two traps, both hit:**
1. *Megamenu bleed* — every page embeds a menu with **other estates'**
   masterplan thumbnails. Filter candidates to the estate's own upload path
   (`/{state}/{slug}/…`) or Newhaven gets saved as The Avenue's plan.
2. *Pin SVGs* — some estates' only SVG is a map-pin marker (`Aston_pin.svg`,
   `Bluestone.svg`, `Brabham-Map-Pin.svg`, `ORIGINAL_Favicon_MapPins.svg`).
   Reject on structure, not just name: a real map is ≥20 KB with dozens of
   `<path>` elements; pins are 1–4 KB with ~3 paths. Aston and Bluestone fall
   back to their masterplan PDFs.

**Coverage (2026-11-06): 27 of 36 estates.** 23 are drawn schematic lot maps;
4 are aerial-based (`lightwood`, `onderra`, `riverbank`, `vantage`). Missing 9 —
`spring-mountain`, `the-landing-strathpine`, `fort-largs`, `south`, `tonsley`,
`woodville-rd`, `keysborough`, `movida-estate`, `hummingbird-rise` — either no
`/for-sale/` page (404) or a townhouse/infill estate with no lot layout to draw.

Curated set: `_peet/masterplans/` (+ `README.md`, `_contact_sheet.png`).
Regenerate: `_peet/fs_survey.py` → `_peet/render_svgs.py`. Raw inputs in
`_peet/fs/`, `_peet/maps/`, `_peet/pdf/`; full-res in `_peet/_hires/` — all
git-ignored.

## No cadastre from Peet's own data
Peet exposes **no lot polygons** anywhere:

- `mapConfig.mapCoordinates` is an estate boundary ring on only 8 of 34 estates
  (74 points total) — a rough hull, not a survey boundary.
- The page's masterplan is a raster PNG on `peet.com.au` (or the SVG above);
  neither is georeferenced.
- No capsule buckets: `{estate}-capsule` returns `NoSuchBucket` for every Peet
  estate tested, and the pages reference no capsule bundle. (Cedar Woods'
  estates do have `{project}-capsule` buckets with real lot polygons — Peet's
  WordPress/Dynamics stack has no equivalent.)

Routes to real geometry, if ever needed: state cadastre (QLD's DCDB is queryable
free via `spatial-gis.information.qld.gov.au` and returns `lot/plan`), joined by
estate + plan number; or ask Peet for the Runway capsule. `lot_number` alone is
a marketing number, so joins are not automatic.

## Runway `sog-p2` — the `Peet/` prefix (resolved)
One anonymous `ListBucket` on Runway's shared bucket exposed a `Peet/` prefix
(#128 of 189). Enumerated 2026-11-06: **3,653 objects, 1.37 GB, 3,591 folders**,
all dated **2017-07 → 2018-12**, types jpg/png/pdf/gif only — **no SVG, no
GeoJSON, no lot status, no cadastre**. Content is estate marketing artwork
(façades, elevations, floorplans) plus 109 PDFs, 91 of them lot-specific site
plans. Folder names are 28-char product IDs from Peet's pre-2019 site
(`display-home?ID=…` era), not `lot_id`s — they do not join.

So the bucket is a dormant asset library, **not** a data source: it contributes
nothing to velocity or geometry. Detail in `peet-leak-from-runway.md`.

## Status codes (behavioral, firm up over 2–3 snapshots)
7 ≈ sold · 2 ≈ available · 4 ≈ future · 1/5/3/8 = mid-states (deposits, holds,
staged releases). `lot_post_status: publish` = currently listed. See the
downloader README for the decode table; this repo trusts week-over-week
movement over labels.

## Spring Mountain anomaly (read before touching velocity)
- The `spring-mountain` community page serves a **leaked aggregate feed**: ~606
  lots whose `lot_name`/`stage_name` belong to OTHER estates (Forestville,
  Yanchep, Tonsley…). It is not that estate's inventory.
- Downloader **excludes it from auto-discovery** (`EXCLUDE` in
  `discover_communities.py`) to avoid double-counting.
- **Decision: keep grabbing it, quarantined.** It costs one GET and may be
  useful (cross-checking estate totals, spotting upstream feed changes).
- Upstream spec (apply in downloader repo only on instruction): fetch
  spring-mountain like any other estate (snapshots namespace by slug, no
  collision) but never let it into estate tables/charts.
- This repo's guard: `QUARANTINE = {'spring-mountain'}` in `scripts/weekly.py`
  strips it from the velocity diff and notes its lot count in WEEKLY.md.
- `_peet/live/` research files **do** contain spring-mountain — exclude it from
  any estate-level aggregation by hand.

## Snapshot cadence
- **Designed: weekly.** Cloud Scheduler → Cloud Run Job (`LOCAL=0`,
  600s timeout). The schedule itself is not versioned in either repo.
- Observed: two full 33-estate runs on 2026-10-24 (plus `TESTING=1` probes).
  `reports/history.csv` has a single row — the weekly series starts here.

## Vanished estates (delisting ≠ sale)
- The downloader **rebuilds its estate list live every run** (index ∪ robots).
  An estate gone from both is silently skipped that run — it is NOT still
  grabbed. Detection, not persistence:
  - `discover_communities.py --notify` raises a Todoist task on new/gone
    estates (only fires when someone/something runs it with `--notify`;
    the scheduled job runs `ppc_downloader.py`, not discovery).
  - `weekly.py` prints a `Gone:` line under Estate changes.
- **No phantom sales by design:** `weekly.py` iterates the *current* run's lots
  and looks each up in the previous run — lots of a vanished estate are absent
  from `cur`, so they are ignored, never counted as sold. First-seen lots are
  likewise labelled, never counted.
- Edge: if a run drops below 20 estates it is not a "full" run and is skipped
  as a diff endpoint.
- Stale-but-present pages (keysborough, onderra: empty `lotConfig`) snapshot as
  0-lot files — harmless. the-landing-strathpine flipped empty → 1 lot; the
  next discovery run promotes it automatically.

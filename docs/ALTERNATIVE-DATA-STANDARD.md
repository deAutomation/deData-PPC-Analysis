# deAutomation Alternative Data — the standard

One pattern, repeated per company. Every alternative-data product we sell is the
same four layers with the company swapped.

**Moniker:** deAutomation Alternative Data · **Hub:** `data.deautomation.co`
**Products:** `<label>.data.deautomation.co`

---

## 1. The four layers

```text
   ┌──────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐
   │ 1. DOWNLOADER    │──▶│ 2. BUCKET    │──▶│ 3. ETL       │──▶│ 4. FIRESTORE    │
   │ weekly snapshot  │   │ GCS raw      │   │ normalise +  │   │ canonical       │
   │ of the public    │   │ snapshots,   │   │ diff + write │   │ schema, per    │
   │ source           │   │ never edited │   │ metrics      │   │ company         │
   └──────────────────┘   └──────────────┘   └──────────────┘   └────────┬────────┘
                                                                        │
                                              ┌─────────────────────────┴──────────┐
                                              ▼                                    ▼
                                    ┌──────────────────┐                ┌──────────────────┐
                                    │ 5. PRODUCT SITE  │◀── entitlement ▶│ 6. HUB           │
                                    │ <label>.data.…   │     check        │ data.deautomation.co
                                    │ reads Firestore  │                │ login · Stripe · │
                                    └──────────────────┘                │ entitlements     │
                                                                        └──────────────────┘
```

A **research repo** sits beside every product and feeds none of it.

| Layer | Repo | Rule |
|---|---|---|
| Downloader | `deData-<CODE>-MasterplanDownloader` | read-only from everywhere else; snapshots only |
| Bucket | `gs://masterplans/<label>/masterplans/{json,csv}/` | immutable; gzipped; never hand-edited |
| ETL | `deData-<CODE>-ETL-Pipeline` | production only; no notebooks |
| Product site | `data.deautomation.co-<label>` | UI + entitlement check; no raw data |
| Hub | `data.deautomation.co` | identity, orders, entitlements — one place |
| Research | `deData-<CODE>-Analysis` | messy is fine; nothing reads from it |

**Current estate**

| Code | Label | Downloader | ETL | Site | Status |
|---|---|---|---|---|---|
| CWP | `cwp` | `deData-CWP-MasterplanDownloader` | `deData-CWP-ETL-Pipeline` | `data.deautomation.co-cwp` | on sale |
| SGP | `sgp` | `deData-SGP-MasterplanDownloader` | `deData-SGP-ETL-Pipeline` | — | by invitation |
| PPC | `ppt` | `deData-PPC-MasterplanDownloader` | `deData-PPC-ETL-Pipeline` | to build | by invitation |
| LIC | `lic` | — | `deData-LIC-ETL-Pipeline` | retired | archived |

## 2. Contracts

### 2.1 Snapshot (layer 1 → 2)

```
gs://masterplans/<label>/masterplans/json/{YYYY-MM-DD}_{HH-MM-SS}-<slug>-masterplan-data-<estate>.json.gz
```

- gzipped, `content-encoding: gzip`
- one object per estate per run; a run is every object sharing the timestamp
- a run is **full** when it carries ≥20 estates — partial runs are never a diff
  endpoint

### 2.2 Firestore schema (layer 3 → 4)

Identical for every company, so one front end reads all of them:

```text
/{COMPANY}/masterplan-data/
  communities/{slug}/
    runs/{YYYY-MM-DD}/parts/{0000..}        # full unit list, that date
    current/units/parts/{0000..}            # latest state
    status_counts/{YYYY-MM-DD}              # the document the site reads
  processed_blobs/{ts}:{slug}               # idempotency
```

`status_counts` is the public interface between ETL and site:

| field | meaning |
|---|---|
| `counts` | `{label: n, …, total}` for the run |
| `incremental_sold` | lots that became Sold vs the previous run; `null` on a first run, never `0` |
| `incremental_sold_revenue` | sum of the **last asking price** for those lots; `null` if none priced |
| `incremental_sold_price_missing` | how many sales had no price — always shipped with revenue |
| `cumulative_sold_revenue` | all priced sold lots in the current state |
| `status_changes` | `[{unit_id, prev_status, new_status, observed_at}]` |
| `coverage` | `{level: full|partial|first_run, prev_units, cur_units}` |
| `baseline_date` | the run this diff was measured against |
| `written_at` | ISO timestamp |

Chunk large arrays at ~900 KB — Firestore documents cap at 1 MB.

### 2.3 Label vocabulary (shared, do not fork)

`Sold · Available · Future Release · Reserved · Unreleased · On Hold · Withdrawn`

Sources differ (CWP has its own status text, Peet uses numeric codes), but the
vocabulary does not. Map at the edge; never rename a label to suit one estate.
Unknown codes surface as `Unknown (<code>)` rather than disappearing.

### 2.4 Entitlements (4 → 5)

```http
GET https://data.deautomation.co/api/entitlements?package=<literal label>
Cookie: da_session=...
→ {"packages": [{"label": "cwp", "edition": "2026-11", "expires_at": 1793932800.0}]}
```

- the label is a **literal in your code**, never from a URL or form field
- empty `packages` = refusal → 403 page
- `401` = not signed in → redirect to `https://data.deautomation.co/login?return=<host+path>`
- `expires_at` is authoritative; fail closed on timeout; cache allow never, deny <60s

The product site never mints a session, never sets the cookie, never trusts the
browser.

## 3. Onboarding a new company

1. **Register the label** — three letters, unique, permanent. Add it to
   `HUB_PACKAGES` in the hub's `cloudbuild.yaml` (comma list). A label is a
   billing identity: never reuse a retired one.
2. **Downloader** — new repo from the existing one; discovery must be live
   (index ∪ sitemap), never hardcoded IDs. Writes to
   `gs://masterplans/<label>/masterplans/{json,csv}/`, gzipped.
3. **ETL** — new repo from `deData-PPC-ETL-Pipeline` (newest, smallest).
   Keep the schema and label vocabulary; change only the parser.
4. **Firestore** — collection `{COMPANY}`, doc `masterplan-data`; the job's
   service account needs `roles/datastore.user`.
5. **Schedule** — downloader runs first; ETL after it, weekly, same region.
   Schedules are infrastructure, not repo configuration — record them in
   `docs/PROVISIONING.md` of the new project.
6. **Product site** — new repo from `data.deautomation.co-cwp`; reads
   Firestore, checks one entitlement, denies by default.
7. **Stripe** — one product and one payment link per package; the link sells
   that package and nothing else. 12 months of access, not recurring.
8. **DNS** — `gcloud run domain-mappings create` for
   `<label>.data.deautomation.co`; mappings do not support wildcards. DNS stays
   A records on `data.deautomation.co` — a CNAME breaks the product hosts.
9. **Catalogue** — flip the listing in the hub's `dist/index.html` from "by
   invitation" to on sale only when 1–8 are done and the first full ETL run has
   landed.
10. **Verify** — sign in on the hub, open the product, confirm another
    package's buyer is refused on this host.

## 4. Guardrails

- **Listings must be true.** No price, package or sample exists until the
  pipeline has produced one. "By invitation" is the honest default.
- **Delisting is not a sale.** A lot/estate that disappears is ignored, not
  counted — counts come from state transitions, not absence.
- **First-seen is not velocity.** New units are labelled, never counted.
- **Nulls over zeros.** No baseline means `null`, so downstream cannot average a
  fake zero.
- **Revenue needs a price source.** Where the source publishes none (PPC), ship
  counts and a missing-price count — never a synthetic price.
- **One company per repo pair.** Research never feeds production; production
  never reads research.

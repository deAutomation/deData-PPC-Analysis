# STATUS — what exists today

Verified 2026-11-06 against the live projects. This is the operational picture;
[`ALTERNATIVE-DATA-STANDARD.md`](ALTERNATIVE-DATA-STANDARD.md) is the pattern it
should follow.

## Repositories

| Repo | Role | State |
|---|---|---|
| `deData-PPC-MasterplanDownloader` | snapshotter → GCS | running (weekly, observed) |
| `deData-PPC-ETL-Pipeline` | GCS → Firestore | **code complete, not deployed**; has run locally into Firestore |
| `deData-PPC-Analysis` | research (this repo) | active; not in the production path |
| `data.deautomation.co` | hub: catalogue, login, Stripe, entitlements | deployed (`data-catalogue`) |
| `data.deautomation.co-cwp` | CWP product site | deployed (`cwp-data`), healthy |
| `data.deautomation.co-ppt` | PPC product site | **not created** |

## The data

| | |
|---|---|
| Bucket | `gs://masterplans` — prefixes `ppc/…`, `cwp/…` |
| PPC snapshots | 3 runs: 2026-10-24 (33 estates), 2026-10-30 (35), 2026-11-06 (35) |
| Firestore project | **`lic-data-452300`** — database `(default)`, Native, `australia-southeast2` |
| Collections | `ADL · CWP · LIC · PPC · SGP · _users` |

PPC content (loaded 2026-11-06):

```text
PPC/masterplan-data/communities/{slug}   35 estates
  status_counts/2026-10-30   e.g. flagstone: total 738, sold 263, incremental —
  status_counts/2026-11-06              total 742, sold 263, incremental 0
  runs/{date}/parts/…       full unit lists
  current/units/parts/…     latest state
```

Cross-check: the ETL and this repo's `weekly.py` independently produce **38**
first-time sales for the week ending 2026-11-06.

## The services

| Service | Project / region | Host | Note |
|---|---|---|---|
| `data-catalogue` | deautomation / asia-southeast1 | `data.deautomation.co` | `/health` and `/api/session` return **nginx 404** — the hub's app routes are not reachable behind this service |
| `cwp-data` | deautomation / asia-southeast1 | `cwp.data.deautomation.co` | `/health` → `{"ok":true}`; `FIRESTORE_PROJECT=lic-data-452300` |

Domain mappings: `data.deautomation.co` → `data-catalogue`, `cwp.data.deautomation.co`
→ `cwp-data`. No `ppt.` mapping.

## Jobs and schedules

| Job | State |
|---|---|
| `ppc-masterplan-job` | **0 Cloud Run jobs** listed in asia-southeast1 or australia-southeast1 |
| `ppc-etl-job` | not deployed (CI builds from `cloudbuild.yaml`) |

Cloud Scheduler API is **not enabled** on `deautomation`, so no weekly trigger
exists for either PPC job. The downloader nonetheless produces weekly snapshots —
whatever runs it is outside this project's scheduler.

## Identity

- Services run as `data-runtime@deautomation.iam.gserviceaccount.com`.
- Local runs used the service-account key for `lic-data-452300` (read on the
  bucket, write on Firestore). The `deautomation` compute SA can list Firestore
  databases but **cannot create** them.
- `deautomation`'s default database is **Datastore mode**; it cannot hold this
  schema. Do not point an ETL at it.

## Known gaps

1. **ETL not deployed** — the data exists because it was loaded from a
   workstation. Until `ppc-etl-job` runs on a schedule, Firestore will stop
   updating after the current snapshots.
2. **No scheduler** — neither downloader nor ETL has a trigger recorded here.
3. **Hub app routes unreachable** — `data-catalogue` serves nginx 404 on
   `/health` and `/api/session`. Login and entitlements are unverified.
4. **`ppc` not in `HUB_PACKAGES`** — add to the hub's `cloudbuild.yaml`
   (`cwp,sgp` → `cwp,sgp,ppc`); no other hub code change is needed to grant it.
5. **PPC product site and `ppt.` domain** do not exist.
6. **Stripe product** for PPC does not exist.
7. **Revenue coverage** is structurally sparse: all 38 first-time sales moved
   `Reserved → Sold` without ever being published, so none had an asking price.

## Next, in order

1. Deploy `ppc-etl-job` (push already done — CI builds it).
2. Enable Cloud Scheduler; create `ppc-masterplan-weekly` (07:00) and
   `ppc-etl-weekly` (09:00) in `Australia/Adelaide`.
3. Fix or confirm the hub routes, then add `ppc` to `HUB_PACKAGES`.
4. Build `data.deautomation.co-ppt` + map `ppc.data.deautomation.co`.
5. Create the Stripe product/payment link, then flip the catalogue listing.

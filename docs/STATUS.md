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
| `data.deautomation.co-ppc` | PPC product site | **deployed** (`ppc-data`) 2026-11-06; push-to-`main` CI/CD live |

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
| `data-catalogue` | deautomation / asia-southeast1 | `data.deautomation.co` | Python hub live 2026-11-06; `/health` → `{"ok":true,"store":"FirestoreStore"}`; `/api/session` → `{"signed_in":false}`; `/api/entitlements?package=ppc` → 401 |
| `cwp-data` | deautomation / asia-southeast1 | `cwp.data.deautomation.co` | `/health` → `{"ok":true}`; `FIRESTORE_PROJECT=lic-data-452300` |
| `ppc-data` | deautomation / asia-southeast1 | `ppc.data.deautomation.co` | deployed 2026-11-06; `/health` → `{"ok":true,"package":"ppc"}`; entitlement-gated pages 302 to hub sign-in |

Domain mappings: `data.deautomation.co` → `data-catalogue`, `cwp.data.deautomation.co`
→ `cwp-data`, `ppc.data.deautomation.co` → `ppc-data` (certificate ready).
DNS: `data.deautomation.co` is delegated to Cloud DNS `data-zone`
(`ns-cloud-c1–c4`); `clients.deautomation.co` stays in `clients-zone`.

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
3. **Hub mail secrets missing.** The hub is live and Firestore-backed, and the
   full magic-link flow was proven end to end on 6 Nov by surfacing the link in
   logs: `/auth/verify` → 302 to `/account`, `da_session` set for
   `.data.deautomation.co`, `/api/entitlements?package=ppc` returns the package,
   and `ppc.data` then serves 200 (sign-out returns it to 302). What is missing
   is the Mailgun key: no `mailgun-api-key` secret exists, so a real buyer's
   email is never sent. The key was exposed in a chat transcript and must be
   rotated first. The admin console also needs `google-oauth-secret`, and
   Stripe needs `stripe-webhook-secret`.
4. **`ppc` is in `HUB_PACKAGES`** — the deployed hub lists `cwp,sgp,ppc` and
   returns the `ppc` entitlement for a seeded account (verified end to end).
5. **PPC site is live and gated.** `ppc.data.deautomation.co` serves a GTS
   certificate; `/` 302s to the real hub login; `/health` → 200; a valid
   `ppc` entitlement returns 200 and `/charts.json`; a bad cookie is
   rejected to the hub login (302), and 503 is reserved for an unreachable hub. No standing test session was left behind (a manual entitlement
   remains for the owner). The reusable procedure is
   `deautomation-data/development-pipeline/PRODUCT-HOST-RUNBOOK.md`.
6. **Stripe product** for PPC does not exist.
7. **Lot geometry now covers 17 estates.** `scripts/build_geo.py` parses real
   lot footprints from the `/for-sale/` SVG stage groups, joins live feed on
   stage + number, and georeferences by the best available anchor: state
   cadastre parcel fit (QLD/NSW: flagstone, edens-crossing, riverbank,
   village-green, lily, jumping-creek), `mapConfig` ring fit (newhaven,
   elmslie-common, glendalough, little-eagle-nudgee), or sales-centre-anchored
   schematic (cornerstone, elavale, ellery, golden-bay, lakelands,
   millers-row, the-avenue-estate, yanchep-golf-estate). Served as
   `/geo/<slug>.geojson` (smart polygons) with per-method honesty copy on the
   estate page. No geometry for aston / bluestone-mt-barker (pin SVGs, no
   lot shapes) or vantage (aerial PDF only). Method and limits:
   `_peet/geo/README.md`. Key correction: the `mapConfig` ring is decorative
   and can sit ~700 m off the true subdivision (proven at village-green) —
   parcel-fit positions win wherever cadastre exists.
8. **Revenue coverage** is structurally sparse: all 38 first-time sales moved
   `Reserved → Sold` without ever being published, so none had an asking price.

## Next, in order

1. Create the `mailgun-api-key` secret (and `google-oauth-secret`,
   `stripe-webhook-secret` when those surfaces are needed) so hub sign-in can
   send links.
2. Deploy `ppc-etl-job` (push already done — CI builds it).
3. Enable Cloud Scheduler; create `ppc-masterplan-weekly` (07:00) and
   `ppc-etl-weekly` (09:00) in `Australia/Adelaide`.
4. Create the Stripe product/payment link, then flip the catalogue listing.

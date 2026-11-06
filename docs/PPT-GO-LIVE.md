# PPT go-live — from by-invitation to sold

What already exists, what is missing, and the exact steps to put
`ppt.data.deautomation.co` on sale.

The hub repository is **not writable from this checkout**; the changes below
are specified so they can be applied there.

---

## Already in place

| Piece | State |
|---|---|
| Label `ppt` | in the catalogue (`dist/index.html`) and the Log in menu, marked *by invitation* |
| Catalogue card | `#ppt`, "Peet Limited (ASX: PPT) · By invitation", mailto CTA |
| Package registry | **not** in `HUB_PACKAGES` — must be added |
| Stripe product | none |
| ETL | `deData-PPC-ETL-Pipeline` written and tested; not yet deployed or scheduled |
| Product site | does not exist |

## 1. Register the package (hub)

`cloudbuild.yaml` in `data.deautomation.co`, line ~53:

```diff
-        ENV="$ENV@HUB_PACKAGES=cwp,sgp"
+        ENV="$ENV@HUB_PACKAGES=cwp,sgp,ppt"
```

No other hub code change is needed to *grant* the package: entitlements are
keyed `{account_id}:{package_label}`, and `ppt` becomes a valid label the moment
it is in the list. The catalogue card and login dropdown already use it.

## 2. Firestore — **done**

The ETL writes `PPC/masterplan-data/communities/{slug}` into
`lic-data-452300` (the shared alt-data project — **not** `deautomation`, whose
default database is Datastore mode and cannot hold this schema).

Loaded 2026-11-06 from the two synced runs:

```text
PPC: 35 communities, status_counts for 2026-10-30 and 2026-11-06
collections now: ADL  CWP  LIC  PPC  SGP  _users
```

To reload or extend, the job needs only env:

```bash
GOOGLE_APPLICATION_CREDENTIALS=<key> \
FIRESTORE_PROJECT=lic-data-452300 FIRESTORE_COLLECTION=PPC \
python main.py --local-json ../deData-PPC-Analysis/_in --all-dates
```

## 3. Schedule — its own trigger, 2 h after the downloader

PPC's downloader fires at **07:00 `Australia/Adelaide`** (observed in the bucket:
`2026-10-30_07-00-19`, `2026-11-06_07-00-22`). The ETL gets its **own** scheduler
entry, unique in the family, two hours later:

```bash
# downloader (07:00 Wed)
gcloud scheduler jobs create http ppc-masterplan-weekly \
  --location=australia-southeast1 --schedule="0 7 * * 3" --time-zone="Australia/Adelaide" \
  --uri="https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/deautomation/jobs/ppc-masterplan-job:run" \
  --oauth-service-account-email=259851748981-compute@developer.gserviceaccount.com

# ETL (09:00 Wed — 2 h buffer)
gcloud scheduler jobs create http ppc-etl-weekly \
  --location=australia-southeast1 --schedule="0 9 * * 3" --time-zone="Australia/Adelaide" \
  --uri="https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/deautomation/jobs/ppc-etl-job:run" \
  --oauth-service-account-email=259851748981-compute@developer.gserviceaccount.com
```

Prerequisites still missing: Cloud Scheduler API is not enabled on
`deautomation`, and `ppc-etl-job` is not deployed yet (CI builds it from the
repo's `cloudbuild.yaml`).

## 4. Stripe product and payment link

One product, one price, one payment link — the link sells `ppt` only.

1. Stripe → Products → new product **"PPT Alternative Data"**, AUD, excluding GST.
2. Price: 12 months of access (not recurring), matching the CWP package model.
3. Payment link → set **metadata** `package=ppt` (and `edition=YYYY-MM`), which
   the hub's `/webhooks/stripe` reads to grant `{account}:ppt`.
4. Copy the link into the catalogue card only after the webhook grant has been
   tested end-to-end in Stripe test mode.

> Until this exists, the listing must stay "by invitation". A price on the page
> with no working link is a false listing.

## 5. Product site — next block of work

Deferred by decision; this is the shape it should take. Clone
`data.deautomation.co-cwp` (Flask + Firestore + family session) and change only
what differs:

| Change | From (CWP) | To (PPT) |
|---|---|---|
| package label | `cwp` | `ppt` |
| Firestore collection | `CWP` | `PPC` |
| project | `lic-data-452300` | same |
| reads | `status_counts/{date}` | same — never raw `runs/` |
| service name | `cwp-data` | `ppt-data` |
| host | `cwp.data.…` | `ppt.data.deautomation.co` |
| branding / copy | CWP | Peet (ASX: PPC) |

Env it will need (mirroring the live CWP service):

```text
FIRESTORE_PROJECT = lic-data-452300
FIRESTORE_COLLECTION = PPC
PACKAGE_LABEL = ppt
FLASK_SECRET_KEY = <secret: ppt-flask-secret>
```

Login is **not** built here — the site reads `da_session`, asks
`https://data.deautomation.co/api/entitlements?package=ppt`, 403s on an empty
list, and redirects to `data.deautomation.co/login?return=<host+path>` on 401.
The dropdown on the hub stays the single sign-in surface, exactly as with CWP.

Deployment: push to `main` → the repo's GitHub workflow builds `cloudbuild.yaml`
→ Cloud Run service `ppt-data`. Never deploy by hand.

## 6. DNS

```bash
gcloud run domain-mappings create \
  --service=ppt-data \
  --domain=ppt.data.deautomation.co \
  --region=asia-southeast1
```

Then publish exactly the DNS records Google returns. Mappings are per-host, no
wildcards; keep the four A records on `data.deautomation.co`. A CNAME breaks
every product host.

## 7. Flip the listing

Only when 1–6 are done and the first full weekly diff has landed:

- catalogue card: remove `By invitation`, add the price and the Stripe link
- login dropdown: enable the `PPT` entry
- `meta description` / `og:description`: PPT moves out of "by invitation"

## Open questions before selling

1. **Revenue is largely unavailable.** Peet publishes no sale price, and all 38
   sales in the first test week moved `Reserved → Sold` without ever being
   listed. The product should sell **counts and velocity**, with revenue marked
   unavailable — not a revenue series that is mostly nulls.
2. **Estate roster stability.** 35 estates today; the downloader rebuilds the
   list each run, so estates appear and disappear. `coverage` flags big swings,
   but the site copy should say "estates tracked" rather than implying a fixed
   universe.
3. **Cadence honesty.** Weekly snapshots mean sale dates are accurate to the
   pull, not the settlement. Say so on the page.

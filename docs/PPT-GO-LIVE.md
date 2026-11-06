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

## 2. Firestore

The ETL writes `PPC/masterplan-data/communities/{slug}`. First run:

```bash
# after deploy, once
gcloud run jobs execute ppc-etl-job --region=australia-southeast1 --wait
```

Verify one document exists and is small enough to read:

```bash
gcloud firestore documents list --collection-ids=status_counts  # or the console
```

## 3. Schedule the two jobs

The downloader must run before the ETL, weekly:

```bash
gcloud scheduler jobs create http ppc-masterplan-weekly \
  --location=australia-southeast1 --schedule="0 21 * * 3" \
  --uri="https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/deautomation/jobs/ppc-masterplan-job:run" \
  --oauth-service-account-email=259851748981-compute@developer.gserviceaccount.com

gcloud scheduler jobs create http ppc-etl-weekly \
  --location=australia-southeast1 --schedule="30 22 * * 3" \
  --uri="https://australia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/deautomation/jobs/ppc-etl-job:run" \
  --oauth-service-account-email=259851748981-compute@developer.gserviceaccount.com
```

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

## 5. Product site

Clone `data.deautomation.co-cwp` and change four things:

| Change | Where |
|---|---|
| package label `cwp` → `ppt` | the entitlement call |
| Firestore collection `CWP` → `PPC` | data layer |
| read `status_counts/{date}` only | data layer — never raw runs |
| branding / copy | templates and `dist/` |

The session contract is already documented in the hub's `docs/HUB-INTEGRATION.md`:
forward `da_session`, ask `/api/entitlements?package=ppt`, 403 on empty,
redirect to `data.deautomation.co/login?return=…` on 401.

## 6. DNS

```bash
gcloud run domain-mappings create \
  --service=<ppt-site-service> \
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

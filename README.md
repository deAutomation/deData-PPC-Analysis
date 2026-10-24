# deData-PPC-Analysis (Peet — GitHub only)

Weekly sales-velocity analysis on top of `deData-PPC-MasterplanDownloader`
snapshots. **No ETL, no database, no website wiring** — this repo stays on GitHub:
snapshot diffs in, Markdown pack + charts out.

## How it works
`scripts/weekly.py` takes the two latest **full** runs (≥20 estates) and diffs them
lot-by-lot on `(community, lot_id)`:
- available/published → status `7`, or silently delisted ⇒ **sale** (last-asked price)
- `7` → back to available ⇒ **cancellation** (negative sale)
- first-seen lots are labelled, never counted as velocity (same first-seen rule as SGP)

Outputs per run date: `reports/<date>/WEEKLY.md`, `reports/<date>/weekly.csv`,
`charts/<date>_net_sales.png`.

## Run it
```bash
pip install matplotlib   # only dependency
python3 scripts/weekly.py --input /path/to/snapshot-json-dir
```
`--input` is any dir of `*-ppc-website-masterplan-data-*.json`. To run against the
live bucket, sync first: `gcloud storage cp -r gs://masterplans/ppc/masterplans/json ./_in`
then point `--input` at `./_in`.

## Status codes
7 ≈ sold · 2 ≈ available · 4 ≈ future · 1/5/3/8 = mid-states. Decode notes live in the
downloader README; this repo consumes codes as-is and lets week-over-week movement
confirm them.

## Cadence
Run after each weekly snapshot lands. Reports accumulate in `reports/`; charts in
`charts/`. Nothing here ever touches Firestore or the website.

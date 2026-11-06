# Peet — presence in Runway's shared bucket

**Listed:** 2026-11-03 · **Enumerated:** 2026-11-06 · Source: anonymous `ListBucket` on
`sog-p2` · Evidence: [`_peet/peet-prefix-objects.csv`](_peet/peet-prefix-objects.csv)

---

## What the evidence shows

| Item | Value |
|---|---|
| Prefix | `Peet/` |
| Type | Named tenant prefix (not a numeric client ID) |
| Position | 128 of 189 in the sorted listing — between `OxlandGroup` and `PerryHomes-R6` |
| Variants | **None** — no `Peet-R6`, no `-r6dev`, no staging prefix |
| Objects | **3,653** in **3,591** folders |
| Size | **1.37 GB** |
| Types | 3,339 jpg · 191 png · 109 pdf · 12 jpeg · 2 gif |
| Dates | **2017-07-12 → 2018-12-03** — nothing newer |
| Geometry | **None** — no SVG, no GeoJSON |

## What is actually in it

A dormant marketing asset library from Peet's pre-2019 website generation:

- façades, elevations and floorplan renders, many tagged `REA`, `campaign` or `Disclosure`;
- 109 PDFs, of which **91 are lot-specific site plans** (`Greenlea_-_Stage_1_LOT_195.pdf`,
  `Hilbert_Park_-_STAGE_2_LOT_153.pdf`) showing frontage, area and services — 2017–18 vintage;
- a handful of stage release plans.

Folder names are 28-character product IDs (`Peet/00105O1Y1H185F119A9S9D131I9K/`), matching the
`display-home?ID=…` URLs of the era. They are **not `lot_id`s** and do not join to the current
site's integer lot IDs.

## What it tells you

- Peet is a **Runway client**, co-tenanted alongside Cedar Woods in `sog-p2`.
- The single `Peet/` prefix with no `-R6` or dev sibling is unusual — most tenants in that bucket
  carry two or three variants (`Simonds`/`SimondsR6`, `Oxland`/`OxlandGroup`,
  `PulteHomes`/`PulteHomes-USA`). Peet appears not to have been migrated to the R6 naming
  convention, or uses a single tree.
- The library has been untouched for ~8 years, so Runway is still publicly serving a former
  client's 1.37 GB of artwork.

## What it does not give you

No lot status, no prices, no sale records, no buyer data and no lot geometry. It contributes
nothing to the velocity analysis — which runs entirely off the `lotConfig` feed on
peet.com.au. Details in [`AGENTS.md`](./AGENTS.md).

## Context

Peet Limited (ASX: PPC) is an Australian residential developer. The only Peet data in this
bucket is the prefix and the 2017–18 artwork above.

---

*Companions: [`SOG-P2.md`](https://github.com/deAutomation/website-quality-testing-findings)
and `sog-p2-tenants.md` live in the Cedar Woods findings repo, not here.*

# Estate masterplans — dated, curated versions

One PNG per estate per map version, normalised (≤1600 px, 256-colour palette), captured 2026-11-06.

```
masterplans/<estate>/<YYYY-MM-DD>.png     ← one file per dated version
masterplans/index.csv                     ← estate, version_date, map_kind
masterplans/_contact_sheet.png            ← whole set at a glance
```

**Coverage: 27 of 36 estates** — 18 `svg-map`, 4 `image`, 2 `pdf`, 3 `pdf-aerial`.
The date is the map's own version, not the capture date; a re-run finding a newer
`_MP_` file adds a sibling rather than overwriting.

## Source: the lot-page SVG

The lot-selection map is **not** on the marketing page. Every estate with an active
listing serves it as a vector file on `/for-sale/`:

```
https://www.peet.com.au/{state}/{slug}/wp-content/uploads/…/{Slug}_MP_{DDMMYY}.svg
```

Layered (`Base`, `POS`, `HATCH`), 1–3 MB, every lot drawn as a path and numbered — the
closest thing Peet exposes to lot geometry.

Priority per estate:

1. **`svg-map`** — the `_MP_` SVG rendered in headless Chrome.
2. **`pdf`** — masterplan PDF at 150 dpi where no SVG exists (aston, bluestone).
3. **`image`** — `masterplan`-named image on the estate's own path (brabham,
   burns-beach, shorehaven, the-village-at-wellard).
4. **`pdf-aerial`** — orthophoto/aerial plan where no drawn map exists (lightwood,
   onderra, vantage).

## Rendering note

Use **headless Chrome**, the SVGs put their fills in CSS classes and PyMuPDF renders them
as black silhouettes. Chrome needs `--user-data-dir` inside the sandbox:

```bash
chrome --headless=new --no-sandbox --user-data-dir=/tmp/cprof \
       --window-size=<viewBox aspect> --screenshot=out.png file:///abs/path.svg
```

## Curation rules (a masterplan, not a logo)

- **Reject on structure, not just name.** Real maps are ≥20 KB with dozens of `<path>`
  elements; pin markers are 1–4 KB with ~3 paths and render as a giant teardrop.
  Rejected this way: `Aston_pin.svg`, `Bluestone.svg`, `Brabham-Map-Pin.svg`,
  `ORIGINAL_Favicon_MapPins.svg`.
- **Reject name matches** for `pin|logo|icon|favicon|brand|emblem`.
- **Filter to the estate's own upload path.** Every page's megamenu carries *other*
  estates' masterplan thumbnails — without the path filter, Newhaven gets saved as
  The Avenue's plan.

## Map kinds

- **schematic (23)** — drawn lots, roads, open space, amenity icons. The right basis for
  overlaying lot status.
- **aerial (4)** — `lightwood`, `onderra`, `riverbank`, `vantage`: top-down but
  photographic/overlay rather than drawn.

Per-file notes: `cornerstone` and `ellery` are genuinely long narrow estates (tall frames
are correct, not crops); `millers-row` covers the South Morang section only; `little-eagle-nudgee`
is rotated in the source; `glendalough` is sparse (lot pads only).

## Missing (9)

`spring-mountain`, `the-landing-strathpine`, `fort-largs`, `south`, `tonsley`,
`woodville-rd`, `keysborough`, `movida-estate`, `hummingbird-rise` — no `/for-sale/` page
(404) or townhouse/infill estates with no lot layout. `spring-mountain` has no own-path
assets at all, consistent with its quarantined feed (see `../../AGENTS.md`).

## Regenerate

`../fs_survey.py` (find map SVGs) → `../render_svgs.py` (Chrome render). Scratch inputs in
`../pages/`, `../fs/`, `../maps/`, `../pdf/`; full-resolution originals in `../_hires/`
(all git-ignored).

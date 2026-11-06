# Reusable skills and repeat processes (lot-geometry rollout, 2026-11-06)

Common procedures distilled from building smart lot plans for 17 Peet estates.
Each is written to be reusable for the next estate, the next snapshot, or the
next developer (CWP/LIC/SGP use the same Flask stack and similar SVG plans).

## 1. SVG lot-plan parsing (any Peet-style masterplan SVG)

`scripts/build_geo.py::parse_svg` — dependency-free (stdlib `xml.etree` + `re`).

- Walk the tree with an ancestor-id stack; attribute every `rect`/`polygon`/
  `polyline`/`path` whose id starts `lot_` to its nearest `*stage*` group.
- Handle both label dialects: `<text id="lot_name_N">` (direct) and
  `<g id="lot_name_N">` (nested `<text>` inside).
- Flatten path `d` (M/L/H/V/C/Q/A/Z, relative + absolute) by subdividing
  curves; comma- AND space-separated polygon points.
- Element transforms: `translate + rotate + scale` applied to rect corners.
- Smoke test: `python3 scripts/build_geo.py --all` prints shapes/feed/ring per
  estate. Expect rect+polygon for lots; `path`-heavy files need the flattener.

## 2. Stage-name normalisation (plan generation vs feed generation)

`norm_stage_for(estate, gid)`:

1. Strip `numbers_/stage(s)_` prefix, lowercase, drop non-alphanumerics.
2. Remove ALL estate words anywhere (every substring of the estate name, e.g.
   `theavenue` inside `theavenuestage10`), then all `stage`/`numbers` words.
3. Release alias: `4release1 → 4a`, `4release2 → 4b`.

Join ladder (record which rung in `metadata.join_method`):

1. `staged` — exact normalised match (most estates).
2. `stage-remap` — zero key overlap but equal group counts (plan 1–6 vs feed
   301–306): pair size-ordered groups.
3. `bare-renumber` — plan has no stage split: bare lot numbers, only if the
   number is unique across the whole feed.

Bare-number lesson (village-green): lot numbers are reused across stages, so
bare joins inflate. Never colour by bare join without the uniqueness guard.

## 3. Georeferencing ladder (best anchor available)

1. **`parcel-scored`** — state cadastre. Coarse-to-fine search over
   translation (±1.5 km grid) × rotation × scale; score = share of lot
   centroids inside residential parcels (150–3,000 m² by shoelace area) with
   compatible area (log-ratio < ln 3). Numpy-vectorised bbox prefilter, exact
   ray-cast on hits, sample ≤250 shapes for the search.
2. **`ring-centroid`** — `mapConfig` ring: rotation/scale search, score = %
   inside ring. WARNING: rings are decorative (village-green's sat 700 m off
   at 98.5% inside). Use only where no cadastre exists.
3. **`anchor-envelope`** — sales-centre lat/lng from
   `data-sales-lat/lng` on the community page, scale ≈ 1.5 km / plan extent.
   Schematic — the site copy must say so.

QA each fit with `scripts/verify_overlay.py <slug>`: plan lots (blue) over
residential parcels (tan). Ship at ≥~55% with visible block alignment;
below that the plan is the wrong generation or wrong scale (lily: block
outlines, kept but flagged).

## 4. Open cadastre access (no keys)

- **QLD** (`spatial-gis.information.qld.gov.au/.../LandParcelPropertyFramework/MapServer/4/query`):
  layer **4**, not 1 (group layer 400s). Point query needs `where=1=1`.
  Page by `objectid` ranges (lowercase field), not `resultOffset`.
- **NSW** (`maps.six.nsw.gov.au/.../NSW_Cadastre/MapServer/9/query`): layer 9,
  envelope `xmin,ymin,xmax,ymax`, `resultOffset` works. Fields `lotnumber`,
  `planlabel`, `shape_Area`.
- VIC 403 / WA keyed / SA unclear → fall back to ring/anchor tiers.
- Cache raw parcels in `_peet/cadastre/<slug>.parcels.json` (git-ignored if
  large; the QLD files are ~2–3 MB each).

## 5. Publishing geometry to the product site

1. Copy `*.smart.geojson` → webapp `static/geo/` (same basename).
2. `geo_for` prefers `.smart.geojson`, falls back to legacy `.geojson`.
3. `geo_svg` handles both: Polygon lots (`kind: lot polygon`), legacy Points,
   boundary ring-or-hull (`kind: estate boundary`). Returns counts + method
   metadata for the card; Leaflet renders polygons via `L.geoJSON` with the
   palette contract (sold `#F15A29`, avail `#1f6f8b`, other `#d7dde5`).
4. Estate template copy is method-aware: parcel %, ring %, or schematic
   disclaimer; join-method note (remap/bare) when applicable.
5. Tests (`tests/test_app.py::GeoTests`): smart-preferred loading, polygon
   counts, legacy-point rendering, `/geo/<slug>.geojson` endpoint, estate
   card render. Run `python3 -m unittest discover -s tests`.

## 6. Sandbox multi-repo moves

Writes into a secondary checkout (webapp, ETL) from a shell whose cwd is the
primary workspace are denied — re-run the command with `workdir` set to the
target repo root (foreground and background alike). Reads work from anywhere.

## 8. Rotation QA (learned 2026-11-06 — read before trusting a fit)

Parcel-fit rotation can settle in local minima that look plausible in numbers
but shear blocks across streets (riverbank 134°). Rules:

- **Always render the verify overlay** (`scripts/verify_overlay.py`): blue
  plan lots over tan residential parcels. Blocks must sit ON parcels with
  matching street grain, not merely near them.
- **Centroid-in-parcel scoring is blind on regular grids**: a twisted fit
  still drops centroids in neighbouring parcels (VG 249° outscored the true
  332°). Vertex-footprint scoring ranks better but its absolute values stay
  low on schematic plans (wide drawn roads) — judge by eye, not by score.
- **Abandoned approaches**: per-parcel edge-orientation agreement (drafting
  conventions differ — VG's longest edges are side boundaries, parcels'
  are frontages); global street-grid histogram (bbox mixes suburbs; also a
  y-down/y-up frame trap in SVG coords).
- **Pin verified fits** in `_peet/geo/fits.json`
  (`{rotation_deg, scale, tx_m, ty_m}`); `build_one` uses pins verbatim.
  Search proposes, human verifies, pin locks. Re-verify after any plan
  version change.
- **When to drop**: lily's plan draws block outlines, not lots, and every
  fit scores ~0 — no map card (lot matrix covers it) beats a wrong map.

- New `_MP_DDMMDD` SVG version on the `/for-sale/` page.
- Fit score drops (plan extended into unsurveyed stages).
- Feed stages rename (new `stage-remap` pairs).
- Cadastre refresh (nightly upstream; re-pull bbox parcels).

Command: `python3 scripts/build_geo.py <slug>` (+ preview auto-written),
verify overlay, copy to webapp, run tests, push both repos.

## 9. Refit triggers (when to rebuild an estate)

- New `_MP_DDMMDD` SVG version on the `/for-sale/` page.
- Fit score drops (plan extended into unsurveyed stages).
- Feed stages rename (new `stage-remap` pairs).
- Cadastre refresh (nightly upstream; re-pull bbox parcels).

Command: `python3 scripts/build_geo.py <slug>` (+ preview auto-written),
verify overlay, copy to webapp, run tests, push both repos.

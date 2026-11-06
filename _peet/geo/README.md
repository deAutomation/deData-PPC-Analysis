# Lot geometry — real footprints for 17 estates

Peet publishes **no lot polygons**. The only vector source is the `/for-sale/`
SVG map, which draws every lot as a shape (`rect`/`polygon`/`polyline`/`path`
with `lot_<n>` ids inside `stage_*` groups) and labels it in a separate
`Numbers_*` layer. We recover the shapes, not just the label anchors.

## Pipeline (`scripts/build_geo.py`)

1. **Parse** `_peet/maps/<slug>.svg`: shapes by `(stage-group, lot-number)`,
   both label dialects (`<text id="lot_name_N">`, `<g id="lot_name_N">`),
   path `d` flattened (lines + subdivided curves).
2. **Join** live feed `_peet/live/<slug>.json` on normalised
   `(stage, lot-number)`. Normaliser strips estate tokens anywhere, maps
   `4_Release_1 → 4A` etc. Fallbacks in order: staged → stage-remap (equal
   group counts, e.g. plan 1–6 vs feed 301–306) → bare-renumber (plan has no
   stage split). Join method is recorded per file; bare joins require unique
   numbers.
3. **Georeference**, best anchor available:
   - `parcel-scored` — fit plan to state cadastre (QLD ArcGIS, NSW Six Maps).
     Coarse-to-fine search on translation/rotation/scale; score = share of
     lot centroids inside residential parcels with compatible area. Parcels
     cached in `_peet/cadastre/<slug>.parcels.json`.
   - `ring-centroid` — rotation/scale search scoring % inside the
     `mapConfig` ring, centroid-aligned. Used where no cadastre (VIC/WA).
   - `anchor-envelope` — schematic: plan centred on the sales-centre anchor,
     scale ≈ estate/plan extent. Positions are illustrative.
4. **Emit** `_peet/geo/<slug>.smart.geojson`: 1 boundary feature (ring, or
   plan-envelope hull) + N lot polygons with `{lot_number, matched, status,
   stage}`. Plus `-smart-preview.png` and `-verify.png` (lots over parcels).

## Key correction

The `mapConfig` ring is **decorative**. At village-green the ring fit scored
98.5% inside yet sat ~700 m off the true subdivision; the parcel fit drops
blocks exactly onto surveyed parcels. Parcel-fit positions win wherever
cadastre exists; ring-fit positions are approximate.

## Coverage (2026-11-06)

| Estate | Method | Polygons | Joined | Note |
|---|---|---|---|---|
| flagstone | parcel | 2146 | 397 | stage generations overlap well |
| edens-crossing | parcel | 1071 | 54 | |
| riverbank | parcel | 778 | 83 | |
| village-green | parcel | 337 | 49 | ring discarded (700 m off) |
| lily | parcel | 36 | 8 | block outlines, not lots |
| jumping-creek | parcel | 208 | 37 | NSW cadastre |
| newhaven | ring | 1308 | 285 | |
| elmslie-common | ring | 60 | 60 | single plan group |
| glendalough | ring | 100 | 100 | stage-remap 1–6 → 301–306 |
| little-eagle-nudgee | ring | 82 | 51 | bare-renumber |
| cornerstone | anchor | 709 | 75 | |
| elavale | anchor | 494 | 271 | |
| ellery | anchor | 262 | 253 | |
| golden-bay | anchor | 1265 | 248 | |
| lakelands | anchor | 997 | 260 | |
| millers-row | anchor | 71 | 34 | bare-renumber |
| the-avenue-estate | anchor | 684 | 339 | |
| yanchep-golf-estate | anchor | 730 | 279 | |

No geometry: aston + bluestone-mt-barker (pin SVGs, zero lot shapes),
vantage (aerial PDF only). Grey on the map always means "drawn but not
joinable", never "unsold".

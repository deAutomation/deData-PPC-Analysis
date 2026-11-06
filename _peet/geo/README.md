# Lot geometry — what can be georeferenced, and what can't

Peet publishes **no lot polygons**. The only vector source is the `/for-sale/` SVG
map, which draws lots as shapes but labels them in a separate `Numbers_*` layer as
bare numbers at x/y. Those label anchors are what we can recover.

## Method (village-green, worked end-to-end)

1. Parse `id="lot_name_<n>"` inside each `Numbers_<Estate>_Stage_<n>` group:
   338 labels, each with `translate(x y)` and a `tspan` holding the lot number.
2. Take the estate boundary from the live page's `mapConfig.mapCoordinates`
   (23 points) and project both to local metres around the centroid.
3. Search rotation (280–310°) and scale, scoring candidates by the share of lot
   labels that land inside the boundary ring.
4. Best fit: **rotation 288°, scale 2.44, 91.1% of labels inside**.

## Result

| | |
|---|---|
| Features | 1 boundary polygon + 338 lot points |
| Fit quality | 91.1% inside ring |
| Joined to current inventory | **3 of 338** |
| Plan generation | Stage 1, 2, 3, 4 Release 1, 4 Release 2, 5, 6, 7 |
| Current feed stages | Stage 4A, 4B, 13B, 7, 3, 2C |

**The drawing is an older generation than the inventory.** Lot numbers are reused
across stages, so a bare-number join produces false matches (a naive join claimed
49, of which only 3 survive a stage-aware join). Status colouring is therefore
withheld for the rest: grey means *drawn but not joinable*, not *unsold*.

## Where this works better

Stage-aware matching across the 20 estates with map SVGs:

| Estate | Stage-matched lots |
|---|---|
| flagstone | **399 / 2745** |
| elavale | 275 / 1308 |
| lakelands | 55 / 269 |
| village-green | 3 / 246 |

Flagstone is the candidate for a real lot-status map: enough stages still align
that sold/available colouring would be meaningful.

## Honest limits

- Coordinates come from a drawing fitted to a **boundary ring**, not a cadastre.
  Expect metres of error, and no parcel boundaries.
- Only 8 of 34 estates publish a boundary ring at all; the other 12 with maps
  have no anchor and stay in plan-local coordinates.
- True lot polygons and true positions need the state cadastre (QLD DCDB is free)
  or the Runway capsule from Peet.

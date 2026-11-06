#!/usr/bin/env python3
"""QA overlay: fitted plan lots over cadastre parcels (or ring).
Usage: python3 scripts/verify_overlay.py <slug> [--save-only]
Writes _peet/geo/<slug>-verify.png
"""
import json, math, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.collections import PatchCollection

slug = sys.argv[1]
gj = json.load(open(f"_peet/geo/{slug}.smart.geojson"))
lots = [f for f in gj["features"] if f["properties"].get("kind") == "lot polygon"]
ring = next((f for f in gj["features"]
             if f["properties"].get("kind") == "estate boundary"), None)
lons = [c[0] for f in lots for c in f["geometry"]["coordinates"][0]]
lats = [c[1] for f in lots for c in f["geometry"]["coordinates"][0]]
x0, x1, y0, y1 = min(lons), max(lons), min(lats), max(lats)
pad_x, pad_y = (x1 - x0) * 0.08 + 1e-6, (y1 - y0) * 0.08 + 1e-6

fig, ax = plt.subplots(figsize=(12, 10), dpi=110)
import pathlib
pp = pathlib.Path(f"_peet/cadastre/{slug}.parcels.json")
npar = 0
if pp.exists():
    parcels = json.load(open(pp))
    res = []
    for f in parcels:
        for r in (f.get("geometry", {}) or {}).get("rings", []):
            xs = [p[0] for p in r]; ys = [p[1] for p in r]
            if x0 - pad_x <= max(xs) and min(xs) <= x1 + pad_x and \
               y0 - pad_y <= max(ys) and min(ys) <= y1 + pad_y:
                area = abs(sum(xs[i] * ys[(i + 1) % len(ys)] -
                                 xs[(i + 1) % len(xs)] * ys[i]
                                 for i in range(len(xs))) / 2) * 111320**2 * \
                    math.cos(math.radians((y0 + y1) / 2))
                if 150 < area < 3000:
                    res.append(r)
    npar = len(res)
    if res:
        ax.add_collection(PatchCollection(
            [MplPoly(r, closed=True) for r in res],
            facecolor="#ffe9c9", edgecolor="#d9b77c", linewidths=0.2))
lp = [MplPoly(f["geometry"]["coordinates"][0], closed=True) for f in lots]
ax.add_collection(PatchCollection(lp, facecolor="none", edgecolor="#1f6f8b",
                                  linewidths=0.5))
if ring:
    rr = ring["geometry"]["coordinates"][0]
    ax.plot([c[0] for c in rr] + [rr[0][0]], [c[1] for c in rr] + [rr[0][1]],
            color="#1f6f8b", lw=1.6, ls=(0, (5, 4)))
ax.set_xlim(x0 - pad_x, x1 + pad_x)
ax.set_ylim(y0 - pad_y, y1 + pad_y)
ax.set_aspect("equal")
m = gj["metadata"]
ax.set_title(f"{slug}: plan lots (blue) over {npar} residential parcels (tan) "
             f"[{m.get('method')} score={m.get('fit_inside')}]" if npar else
             f"{slug}: plan lots (blue) + ring [{m.get('method')} score={m.get('fit_inside')}]")
fig.tight_layout()
out = f"_peet/geo/{slug}-verify.png"
fig.savefig(out)
print("saved", out, f"lots={len(lots)} parcels={npar}", m)

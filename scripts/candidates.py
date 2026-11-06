#!/usr/bin/env python3
"""Render diverse fit candidates for visual judging.
Usage: python3 scripts/candidates.py <slug>
Writes _peet/geo/<slug>-candidates.png (2x2: centroid-best, vertex-best,
centroid-runnerup, vertex-runnerup) + prints params for fits.json.
"""
import json, math, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.collections import PatchCollection

sys.path.insert(0, "scripts")
exec(open("scripts/build_geo.py").read().split('if __name__')[0].split(
    "def build_one")[0])

slug = sys.argv[1]
shapes, labels = parse_svg(slug)
parcels, anchor = parcel_rings(slug)
res = residential(parcels)

# shared prep (mirror fit_parcels internals)
import numpy as _np
keys = sorted(shapes.keys())
use = {k: shapes[k] for k in keys}
allp = [p for v in shapes.values() for p in v]
cx = sum(p[0] for p in allp) / len(allp)
cy = sum(p[1] for p in allp) / len(allp)
cents = []
areas = []
for pts in use.values():
    n = len(pts)
    cents.append((sum(p[0] for p in pts) / n - cx,
                  sum(p[1] for p in pts) / n - cy))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    areas.append(abs(sum(xs[i] * ys[(i + 1) % n] - xs[(i + 1) % n] * ys[i]
                       for i in range(n)) / 2))
VERTS = [[(x - (cents[i][0] + cx), y - (cents[i][1] + cy)) for x, y in pts]
         for i, pts in enumerate(use.values())]
C = _np.array(cents)
A_plan = _np.array(areas)
P = res
bboxes = _np.array([b for _, _, b, _, _ in P])
parea = _np.array([a for _, _, _, a, _ in P])
xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
plan_ext = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
seed = 1500.0 / plan_ext


def eval_at(tx, ty, deg, s):
    A = math.radians(deg)
    ca, sa = math.cos(A), math.sin(A)
    RX = C[:, 0] * s * ca - C[:, 1] * s * sa + tx
    RY = C[:, 0] * s * sa + C[:, 1] * s * ca + ty
    x0, y0, x1, y1 = bboxes[:, 0], bboxes[:, 1], bboxes[:, 2], bboxes[:, 3]
    hit = ((RX[:, None] >= x0) & (RX[:, None] <= x1) &
           (RY[:, None] >= y0) & (RY[:, None] <= y1))
    ar = _np.abs(_np.log((A_plan * s * s)[:, None] / parea + 1e-9))
    hit = hit & (ar < math.log(3))
    idx = _np.argwhere(hit)
    cont = {}
    for li, pi in idx[:6000]:
        li, pi = int(li), int(pi)
        if li in cont:
            continue
        pxs, pys, _, _, _ = P[pi]
        if point_in_ring(RX[li], RY[li], list(zip(pxs, pys))):
            cont[li] = pi
    n_in = len(cont)
    tot = 0.0
    for li, pts in enumerate(VERTS):
        pi = cont.get(li)
        if pi is None:
            continue
        pxs, pys, _, _, _ = P[pi]
        ring = list(zip(pxs, pys))
        inside = sum(1 for (vx, vy) in pts
                     if point_in_ring(RX[li] + (vx * ca - vy * sa) * s,
                                      RY[li] + (vx * sa + vy * ca) * s, ring))
        tot += inside / max(len(pts), 1)
    vfrac = tot / max(len(VERTS), 1)
    return n_in / max(len(C), 1), vfrac, cont


results = []
for deg in range(0, 360, 10):
    for f in (0.7, 1.0, 1.5):
        s = seed * f
        for tx in range(-1500, 1501, 500):
            for ty in range(-1500, 1501, 500):
                ci, vf, _ = eval_at(tx, ty, deg, s)
                results.append((ci, vf, deg, s, tx, ty))
results.sort(reverse=True)
# diverse shortlist: best centroid, best vertex, + runners-up far apart
cands = []
seen = []
for ci, vf, deg, s, tx, ty in sorted(results, key=lambda r: -r[0])[:400]:
    if all(abs(deg - d) > 25 or math.hypot(tx - x, ty - y) > 800
           for d, x, y in seen):
        cands.append(("centroid", ci, vf, deg, s, tx, ty))
        seen.append((deg, tx, ty))
    if len(cands) == 2:
        break
seen = []
for ci, vf, deg, s, tx, ty in sorted(results, key=lambda r: -r[1])[:400]:
    if all(abs(deg - d) > 25 or math.hypot(tx - x, ty - y) > 800
           for d, x, y in seen):
        cands.append(("vertex", ci, vf, deg, s, tx, ty))
        seen.append((deg, tx, ty))
    if len(cands) == 4:
        break

lat0, lng0 = anchor
R = math.cos(math.radians(lat0))
par = json.load(open(f"_peet/cadastre/{slug}.parcels.json"))
fig, axes = plt.subplots(2, 2, figsize=(16, 14), dpi=100)
for ax, (tag, ci, vf, deg, s, tx, ty) in zip(axes.flat, cands):
    A = math.radians(deg)
    ca, sa = math.cos(A), math.sin(A)
    ll = {}
    for k, pts in shapes.items():
        ll[k] = [[lng0 + ((x - cx) * s * ca - (y - cy) * s * sa + tx) / (111320 * R),
                  lat0 + ((x - cx) * s * sa + (y - cy) * s * ca + ty) / 111320]
                 for x, y in pts]
    lons = [c[0] for v in ll.values() for c in v]
    lats = [c[1] for v in ll.values() for c in v]
    pp = []
    for f in par:
        for r in (f.get("geometry", {}) or {}).get("rings", []):
            px = [p[0] for p in r]; py = [p[1] for p in r]
            if min(lons) - .004 <= max(px) and min(px) <= max(lons) + .004 and \
               min(lats) - .004 <= max(py) and min(py) <= max(lats) + .004:
                area = abs(sum(px[i] * py[(i + 1) % len(py)] -
                                 px[(i + 1) % len(px)] * py[i]
                                 for i in range(len(px))) / 2) * 111320**2 * \
                    math.cos(math.radians((min(lats) + max(lats)) / 2))
                if 150 < area < 3000:
                    pp.append(r)
    ax.add_collection(PatchCollection(
        [MplPoly(r, closed=True) for r in pp],
        facecolor="#ffe9c9", edgecolor="#d9b77c", linewidths=0.2))
    ax.add_collection(PatchCollection(
        [MplPoly(v + [v[0]], closed=True) for v in ll.values()],
        facecolor="none", edgecolor="#1f6f8b", linewidths=0.5))
    ax.set_xlim(min(lons) - .003, max(lons) + .003)
    ax.set_ylim(min(lats) - .003, max(lats) + .003)
    ax.set_aspect("equal")
    ax.set_title(f"{tag} c={ci:.2f} v={vf:.2f} rot={deg} s={s:.2f} tx={tx} ty={ty}")
    print(f"CANDIDATE {tag} centroid={ci:.3f} vertex={vf:.3f} rot={deg} "
          f"scale={s:.3f} tx={tx} ty={ty}")
fig.suptitle(f"{slug}: fit candidates — pick winner for fits.json")
fig.tight_layout()
fig.savefig(f"_peet/geo/{slug}-candidates.png")
print("saved", f"_peet/geo/{slug}-candidates.png")

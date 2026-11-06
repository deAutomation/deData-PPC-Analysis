#!/usr/bin/env python3
"""General lot-plan builder: SVG stage shapes -> fitted GeoJSON + preview.

Usage:
    python3 scripts/build_geo.py village-green
    python3 scripts/build_geo.py --all

Per estate:
  1. Parse _peet/maps/<slug>.svg — rect/polygon/polyline/path shapes with
     lot_<n> ids inside stage_* groups (any case), labels from numbers_* groups
     (both <text id=lot_name_N> and <g id=lot_name_N> dialects).
  2. Join live feed _peet/live/<slug>.json on (normalised stage, lot number).
  3. Georeference: mapConfig ring fit if ring>=4 pts, else sales-centre anchor
     with scale search scored against QLD cadastre parcels where available.
  4. Emit _peet/geo/<slug>.smart.geojson + preview png.
"""
import json, math, re, sys, glob, os, pathlib
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
MAPS = "_peet/maps"
LIVE = "_peet/live"
PAGES = "_peet/pages"
OUT = "_peet/geo"
CAD = "_peet/cadastre"


def norm_stage(s):
    s = re.sub(r"^(numbers|stages?)_", "", s or "", flags=re.I)
    s = re.sub(r"^[^_]*?_", "", s, count=0)  # placeholder
    s = re.sub(r"[^a-z0-9]+", "", (s or "").lower())
    return s


# Release_N -> letter alias (Peet plan vs feed naming, e.g. Village Green)
RELEASE_ALIAS = {"release1": "a", "release2": "b", "release3": "c",
                 "release_1": "a", "release_2": "b"}


def norm_stage_for(feed_estate, plan_gid):
    """Reduce a plan group id or feed stage name to a comparable stage key."""
    g = re.sub(r"^(numbers|stages?)_", "", plan_gid or "", flags=re.I)
    g = re.sub(r"[^a-z0-9]+", "", g.lower())
    words = re.sub(r"[^a-z0-9]+", " ", (feed_estate or "").lower()).split()
    toks = set(words) | {"".join(words)}
    # also partial concatenations (theavenue from the avenue estate)
    for i in range(len(words)):
        for j in range(i + 1, len(words) + 1):
            toks.add("".join(words[i:j]))
    for tok in sorted(toks, key=len, reverse=True):
        if tok and len(tok) >= 3:
            g = g.replace(tok, "")
    g = g.replace("stage", "").replace("numbers", "")
    # release aliases: 4release1 -> 4a
    for k, v in RELEASE_ALIAS.items():
        kk = re.sub(r"[^a-z0-9]+", "", k)
        if g.endswith(kk):
            g = g[: -len(kk)] + v
    return g


def parse_transform(t):
    m = re.search(r"translate\(([-\d.]+)[ ,]([-\d.]+)\)", t or "")
    tx, ty = (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)
    r = re.search(r"rotate\(([-\d.]+)\)", t or "")
    a = math.radians(float(r.group(1))) if r else 0.0
    sc = re.search(r"scale\(([-\d.]+)(?:[ ,]([-\d.]+))?\)", t or "")
    sx = float(sc.group(1)) if sc else 1.0
    sy = float(sc.group(2) or sc.group(1)) if sc else 1.0
    return tx, ty, a, sx, sy


def xform(px, py, tx, ty, a, sx=1.0, sy=1.0):
    px, py = px * sx, py * sy
    ca, sa = math.cos(a), math.sin(a)
    return tx + px * ca - py * sa, ty + px * sa + py * ca


def rect_corners(el):
    x, y = float(el.get("x", 0)), float(el.get("y", 0))
    w, h = float(el.get("width", 0)), float(el.get("height", 0))
    tx, ty, a, sx, sy = parse_transform(el.get("transform"))
    return [xform(px, py, tx, ty, a, sx, sy) for px, py in
            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]]


def poly_pts(el):
    raw = el.get("points", "").replace(",", " ").split()
    try:
        return [(float(raw[i]), float(raw[i + 1])) for i in range(0, len(raw) - 1, 2)]
    except ValueError:
        return []


TOKEN = re.compile(r"[MmLlHhVvCcQqSsTtAaZz]|-?\d*\.?\d+(?:e[-+]?\d+)?", re.I)


def path_parse(d):
    """Minimal SVG path -> polyline points. Curves flattened by subdivision."""
    toks = TOKEN.findall(d or "")
    pts, cur, start, i = [], (0.0, 0.0), None, 0
    cmd = None
    def arg():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        if re.fullmatch(r"[MmLlHhVvCcQqSsTtAaZz]", toks[i], re.I):
            cmd = toks[i]; i += 1
        if cmd is None:
            i += 1
            continue
        c = cmd.upper()
        rel = cmd != c
        if c == "M":
            x, y = arg(), arg()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            start = cur
            pts.append(cur)
            cmd = "l" if rel else "L"
        elif c == "L":
            x, y = arg(), arg()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            pts.append(cur)
        elif c == "H":
            x = arg()
            cur = (cur[0] + x, cur[1]) if rel else (x, cur[1])
            pts.append(cur)
        elif c == "V":
            y = arg()
            cur = (cur[0], cur[1] + y) if rel else (cur[0], y)
            pts.append(cur)
        elif c == "C":
            x1, y1, x2, y2, x, y = arg(), arg(), arg(), arg(), arg(), arg()
            if rel:
                x1, y1, x2, y2, x, y = cur[0]+x1, cur[1]+y1, cur[0]+x2, cur[1]+y2, cur[0]+x, cur[1]+y
            p0 = cur
            for k in range(1, 7):
                t = k / 6
                mt = 1 - t
                bx = mt**3*p0[0]+3*mt*mt*t*x1+3*mt*t*t*x2+t**3*x
                by = mt**3*p0[1]+3*mt*mt*t*y1+3*mt*t*t*y2+t**3*y
                pts.append((bx, by))
            cur = (x, y)
        elif c == "Q":
            x1, y1, x, y = arg(), arg(), arg(), arg()
            if rel:
                x1, y1, x, y = cur[0]+x1, cur[1]+y1, cur[0]+x, cur[1]+y
            p0 = cur
            for k in range(1, 5):
                t = k / 4
                mt = 1 - t
                pts.append((mt*mt*p0[0]+2*mt*t*x1+t*t*x, mt*mt*p0[1]+2*mt*t*y1+t*t*y))
            cur = (x, y)
        elif c in ("Z",):
            if start:
                pts.append(start)
            cmd = None
        elif c == "A":
            # arc: rx ry rot large sweep x y -> approximate as line to endpoint
            _, _, _, _, _, x, y = arg(), arg(), arg(), arg(), arg(), arg(), arg()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            pts.append(cur)
        else:  # S T etc: consume 2-4 numbers blindly
            try:
                x, y = arg(), arg()
                cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
                pts.append(cur)
            except IndexError:
                break
    return pts


def parse_svg(slug):
    """Return (shapes, labels): shapes[(stage_gid, lotnum)] = pts (plan-local);
    labels {stage_gid: [numbers]}."""
    root = ET.parse(f"{MAPS}/{slug}.svg").getroot()
    shapes, labels = {}, {}
    # ancestor stage group for each shape
    def stage_of(el, tree_path):
        for gid in reversed(tree_path):
            if gid and "stage" in gid.lower():
                return gid
        return ""
    # walk with ancestor stack
    def walk(el, stack):
        gid = el.get("id", "") or ""
        stack = stack + [gid]
        tag = el.tag.replace(NS, "")
        if tag in ("rect", "polygon", "polyline", "path"):
            lid = gid
            if lid.startswith("lot_") or lid.startswith("lot-"):
                num = re.sub(r"^lot[-_]", "", lid).rstrip("-")
                if tag == "rect":
                    pts = rect_corners(el)
                elif tag == "path":
                    pts = path_parse(el.get("d", ""))
                    # apply element transform
                    tx, ty, a, sx, sy = parse_transform(el.get("transform"))
                    if tx or ty or a or sx != 1.0 or sy != 1.0:
                        pts = [xform(x, y, tx, ty, a, sx, sy) for x, y in pts]
                else:
                    pts = poly_pts(el)
                if len(pts) >= 3:
                    shapes[(stage_of(el, stack), num)] = pts
        # numbers groups: collect digit tspans
        if gid and "number" in gid.lower():
            nums = [t.text.strip() for t in el.iter(NS + "tspan")
                    if t.text and t.text.strip().isdigit()]
            if nums:
                labels.setdefault(gid, set()).update(nums)
        for ch in list(el):
            if isinstance(ch.tag, str):
                walk(ch, stack)
    walk(root, [])
    return shapes, {k: sorted(v) for k, v in labels.items()}


def load_feed(slug):
    live = json.load(open(f"{LIVE}/{slug}.json"))
    cfg = live.get("cfg", {})
    lots = cfg.get("all_lots_with_status", [])
    ring = cfg.get("mapConfig", {}).get("mapCoordinates", []) or []
    estate = None
    if lots:
        estate = (lots[0].get("lot_name") or "").rsplit(" Lot ", 1)[0]
    return lots, ring, estate


def sales_anchor(slug):
    txt = open(f"{PAGES}/{slug}.html", encoding="utf-8", errors="ignore").read()
    m = re.search(r'data-sales-lat="([^"]*)"\s*[^>]*data-sales-lng="([^"]*)"', txt)
    if m and m.group(1) and m.group(2):
        return float(m.group(1)), float(m.group(2))
    return None, None


# ---------------------------------------------------------------- georeference

def point_in_ring(px, py, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def fit_ring(shapes, ring):
    """Search rotation+scale mapping plan-local -> lon/lat. Translation aligns
    centroids. Returns (lonlat_pts dict, best)."""
    import math as _m
    allp = [p for v in shapes.values() for p in v]
    cx = sum(p[0] for p in allp) / len(allp)
    cy = sum(p[1] for p in allp) / len(allp)
    clon = sum(c[1] for c in ring) / len(ring)
    clat = sum(c[0] for c in ring) / len(ring)
    R = _m.cos(_m.radians(clat))
    xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
    plan_w = max(xs) - min(xs) or 1
    plan_h = max(ys) - min(ys) or 1
    lon0, lon1 = min(c[1] for c in ring), max(c[1] for c in ring)
    lat0, lat1 = min(c[0] for c in ring), max(c[0] for c in ring)
    ring_w = (lon1 - lon0) * 111320 * R
    ring_h = (lat1 - lat0) * 111320
    base_scale = max(ring_w / plan_w, ring_h / plan_h)
    ring_xy = [((c[1] - clon) * 111320 * R, (c[0] - clat) * 111320) for c in ring]
    best = (0, None, None)
    for deg in range(0, 360, 2):
        A = _m.radians(deg)
        ca, sa = _m.cos(A), _m.sin(A)
        for f in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
            s = base_scale * f
            n_in = n_tot = 0
            for (gid, num), pts in shapes.items():
                px = sum(p[0] for p in pts) / len(pts) - cx
                py = sum(p[1] for p in pts) / len(pts) - cy
                rx, ry = (px * s * ca - py * s * sa, px * s * sa + py * s * ca)
                n_tot += 1
                if point_in_ring(rx, ry, ring_xy):
                    n_in += 1
            score = n_in / max(n_tot, 1)
            if score > best[0]:
                best = (score, deg, s)
    score, deg, s = best
    A = _m.radians(deg)
    ca, sa = _m.cos(A), _m.sin(A)
    def project(px, py):
        dx, dy = (px - cx) * s, (py - cy) * s
        return [clon + (dx * ca - dy * sa) / (111320 * R),
                clat + (dx * sa + dy * ca) / 111320]
    return project, {"rotation_deg": deg, "scale": s, "fit_inside": score,
                     "method": "ring-centroid"}


def parcel_rings(slug):
    """Load cadastre parcels -> (rings_xy_m, areas, anchor lonlat). Rings in
    metres around sales anchor. Supports QLD (rings) and NSW (rings) dialects."""
    import numpy as _np
    p = pathlib.Path(f"{CAD}/{slug}.parcels.json")
    if not p.exists():
        return None
    feats = json.load(open(p))
    lat0, lng0 = sales_anchor(slug)
    R = math.cos(math.radians(lat0))
    out = []
    for f in feats:
        g = f.get("geometry", {}) or {}
        rings = g.get("rings", []) or []
        attrs = f.get("attributes", {}) or {}
        for r in rings:
            if len(r) < 4:
                continue
            xy = [((x - lng0) * 111320 * R, (y - lat0) * 111320) for x, y in r]
            out.append((xy, attrs))
    return out, (lat0, lng0)


def _dominant_angle(xs, ys):
    """Angle of the longest edge (mod 180°), in radians."""
    n = len(xs)
    best, blen = 0.0, -1.0
    for i in range(n):
        dx = xs[(i + 1) % n] - xs[i]
        dy = ys[(i + 1) % n] - ys[i]
        L = dx * dx + dy * dy
        if L > blen:
            blen = L
            best = math.atan2(dy, dx) % math.pi
    return best


def residential(xy_list, lo=150, hi=3000):
    """Filter parcel rings to residential-size with bbox. Returns list of
    (xs, ys, bbox, area, dominant_angle)."""
    res = []
    for xy, attrs in xy_list:
        xs = [p[0] for p in xy]; ys = [p[1] for p in xy]
        area = abs(sum(xs[i] * ys[(i + 1) % len(ys)] - xs[(i + 1) % len(xs)] * ys[i]
                       for i in range(len(xs))) / 2)
        if lo <= area <= hi:
            res.append((xs, ys, (min(xs), min(ys), max(xs), max(ys)), area,
                        _dominant_angle(xs, ys)))
    return res


def grid_rotation(shapes, parcels_m, nbins=180):
    """Estimate plan->world rotation by aligning street grids.

    Area/length-weighted edge-angle histograms (mod 180°) for plan shapes
    vs nearby residential parcels; circular cross-correlation peak gives
    the rotation (two candidates 180° apart). Returns (deg0, deg1).
    """
    import numpy as _np
    ph = _np.zeros(nbins)
    for pts in shapes.values():
        n = len(pts)
        for i in range(n):
            dx = pts[(i + 1) % n][0] - pts[i][0]
            # Negate dy: plan coords are y-down (SVG), world metres are y-up.
            # The fitter maps +y->north, i.e. it vertically flips the drawing
            # then rotates; measuring plan angles in y-up puts the estimate
            # in the fitter's frame.
            dy = -(pts[(i + 1) % n][1] - pts[i][1])
            L = math.hypot(dx, dy)
            if L > 0:
                ph[int((math.atan2(dy, dx) % math.pi) / math.pi * nbins) % nbins] += L
    wh = _np.zeros(nbins)
    for xs, ys, _, _, _ in parcels_m:
        n = len(xs)
        for i in range(n):
            dx = xs[(i + 1) % n] - xs[i]
            dy = ys[(i + 1) % n] - ys[i]
            L = math.hypot(dx, dy)
            if L > 0:
                wh[int((math.atan2(dy, dx) % math.pi) / math.pi * nbins) % nbins] += L
    if ph.sum() == 0 or wh.sum() == 0:
        return None
    ph /= ph.sum()
    wh /= wh.sum()
    corr = _np.array([sum(ph[(i + k) % nbins] * wh[i] for i in range(nbins))
                      for k in range(nbins)])
    k = int(_np.argmax(corr))
    deg = k / nbins * 180.0
    return deg, (deg + 180.0) % 360.0


def fit_parcels(shapes, parcels_m, anchor, scale_seed=None, max_lots=250,
                fixed_rots=None):
    """Coarse-to-fine search: translation around anchor, rotation, scale.
    Score = fraction of shape centroids inside a residential parcel with
    compatible area. Returns (project, meta)."""
    import numpy as _np
    keys = sorted(shapes.keys())[::max(1, len(shapes) // max_lots)]
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
    C = _np.array(cents)  # (L,2) plan-local rel centroid
    A_plan = _np.array(areas)
    # vertices rel shape centroid (for footprint-overlap scoring).
    # cents[i] is rel the whole-plan centroid, so add (cx, cy) back to get
    # the absolute shape centroid before subtracting.
    VERTS = [[(x - (cents[i][0] + cx), y - (cents[i][1] + cy)) for x, y in pts]
             for i, pts in enumerate(use.values())]
    # plan dominant edge angles (mod pi)
    plan_ang = _np.array([_dominant_angle([p[0] for p in pts], [p[1] for p in pts])
                          for pts in use.values()])
    P = parcels_m  # list of (xs,ys,bbox,area,angle)
    bboxes = _np.array([b for _, _, b, _, _ in P])  # (P,4)
    parea = _np.array([a for _, _, _, a, _ in P])
    pang = _np.array([a for _, _, _, _, a in P])
    xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
    plan_ext = max(max(xs) - min(xs), max(ys) - min(ys)) or 1
    if scale_seed is None:
        # estate ~1.5km across typical
        scale_seed = 1500.0 / plan_ext

    def score_of(tx, ty, deg, s):
        A = math.radians(deg)
        ca, sa = math.cos(A), math.sin(A)
        RX = C[:, 0] * s * ca - C[:, 1] * s * sa + tx
        RY = C[:, 0] * s * sa + C[:, 1] * s * ca + ty
        # broadcast bbox test: (L,1) vs (P,)
        x0, y0, x1, y1 = bboxes[:, 0], bboxes[:, 1], bboxes[:, 2], bboxes[:, 3]
        hit = ((RX[:, None] >= x0) & (RX[:, None] <= x1) &
               (RY[:, None] >= y0) & (RY[:, None] <= y1))
        # area prefilter: |log ratio| < log(3)
        ar = _np.abs(_np.log((A_plan * s * s)[:, None] / parea + 1e-9))
        hit = hit & (ar < math.log(3))
        idx = _np.argwhere(hit)  # (K,2)
        # containing parcel per lot (first area-compatible parcel by bbox order)
        cont = {}
        for li, pi in idx[:6000]:
            li, pi = int(li), int(pi)
            if li in cont:
                continue
            pxs, pys, _, _, _ = P[pi]
            if point_in_ring(RX[li], RY[li], list(zip(pxs, pys))):
                cont[li] = pi
        # vertex-in-parcel fraction: footprint overlap, not just centroid.
        # Centroid-only scoring cannot distinguish twisted fits on regular
        # grids (village-green 249deg scored higher yet straddles streets).
        total = 0.0
        for li, pts in enumerate(VERTS):
            pi = cont.get(li)
            if pi is None:
                continue
            pxs, pys, _, _, _ = P[pi]
            ring = list(zip(pxs, pys))
            inside = 0
            for (vx, vy) in pts:
                wx = RX[li] + (vx * ca - vy * sa) * s
                wy = RY[li] + (vx * sa + vy * ca) * s
                if point_in_ring(wx, wy, ring):
                    inside += 1
            total += inside / max(len(pts), 1)
        return total / max(len(VERTS), 1)

    best = (0, 0.0, 0.0, 0, scale_seed)
    # Full rotation sweep: grid estimates proved unreliable (frame flips),
    # and the blind 15° sweep found every good fit so far. The vertex
    # scorer below is the discriminator; the sweep is the explorer.
    degs = list(range(0, 360, 15))
    for deg in degs:
        for f in (0.5, 0.8, 1.2, 2.0):
            s = scale_seed * f
            for tx in range(-1500, 1501, 300):
                for ty in range(-1500, 1501, 300):
                    sc = score_of(tx, ty, deg, s)
                    if sc > best[0]:
                        best = (sc, tx, ty, deg, s)
    sc, tx, ty, deg, s = best
    # refine, wide first then fine
    for deg2 in range(deg - 30, deg + 31, 3):
        for s2 in (s * 0.85, s, s * 1.18):
            for tx2 in (tx - 150, tx, tx + 150):
                for ty2 in (ty - 150, ty, ty + 150):
                    sc2 = score_of(tx2, ty2, deg2, s2)
                    if sc2 > best[0]:
                        best = (sc2, tx2, ty2, deg2, s2)
    sc, tx, ty, deg, s = best
    for deg2 in range(deg - 3, deg + 4, 1):
        for tx2 in (tx - 40, tx, tx + 40):
            for ty2 in (ty - 40, ty, ty + 40):
                sc2 = score_of(tx2, ty2, deg2, s)
                if sc2 > best[0]:
                    best = (sc2, tx2, ty2, deg2, s)
    sc, tx, ty, deg, s = best
    lat0, lng0 = anchor
    R = math.cos(math.radians(lat0))
    A = math.radians(deg)
    ca, sa = math.cos(A), math.sin(A)
    def project(px, py):
        dx, dy = (px - cx) * s, (py - cy) * s
        mx, my = dx * ca - dy * sa + tx, dx * sa + dy * ca + ty
        return [lng0 + mx / (111320 * R), lat0 + my / 111320]
    return project, {"rotation_deg": deg, "scale": s, "fit_inside": sc,
                     "tx_m": tx, "ty_m": ty, "method": "parcel-scored"}


def _convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [list(p) for p in (lo[:-1] + hi[:-1])]


def build_one(slug, project=None, meta=None):
    """Full pipeline for one estate. Returns (geojson, preview_path)."""
    shapes, labels = parse_svg(slug)
    lots, ring, estate = load_feed(slug)
    feed_by_stage = {}
    for l in lots:
        feed_by_stage.setdefault(norm_stage_for(estate, l.get("stage_name") or ""),
                                 {})[l.get("lot_number")] = l
    shape_stage = {gid: norm_stage_for(estate, gid)
                   for gid in {g for g, _ in shapes}}
    join_method = "staged"
    matched, bare = 0, 0
    feats, lot_feats = [], []
    pins = {}
    pinfile = pathlib.Path(f"{OUT}/fits.json")
    if pinfile.exists():
        pins = json.loads(pinfile.read_text()).get(slug, {})
    if project is None:
        if pins.get("method") == "pinned":
            lat0, lng0 = sales_anchor(slug)
            R = math.cos(math.radians(lat0))
            allp = [p for v in shapes.values() for p in v]
            cx = sum(p[0] for p in allp) / len(allp)
            cy = sum(p[1] for p in allp) / len(allp)
            A = math.radians(pins["rotation_deg"])
            ca, sa, sc = math.cos(A), math.sin(A), pins["scale"]
            tx, ty = pins["tx_m"], pins["ty_m"]
            def project(px, py, _cx=cx, _cy=cy, _s=sc, _la=lat0, _ln=lng0,
                         _R=R, _ca=ca, _sa=sa, _tx=tx, _ty=ty):
                dx, dy = (px - _cx) * _s, (py - _cy) * _s
                return [_ln + (dx * _ca - dy * _sa + _tx) / (111320 * _R),
                        _la + (dx * _sa + dy * _ca + _ty) / 111320]
            meta = {"rotation_deg": pins["rotation_deg"], "scale": sc,
                    "fit_inside": pins.get("fit_inside"),
                    "tx_m": tx, "ty_m": ty, "method": "pinned"}
        elif pathlib.Path(f"{CAD}/{slug}.parcels.json").exists():
            parcels, anchor = parcel_rings(slug)
            res = residential(parcels)
            project, meta = fit_parcels(shapes, res, anchor)
        elif len(ring) >= 4:
            project, meta = fit_ring(shapes, ring)
        else:
            lat0, lng0 = sales_anchor(slug)
            R = math.cos(math.radians(lat0))
            allp = [p for v in shapes.values() for p in v]
            cx = sum(p[0] for p in allp) / len(allp)
            cy = sum(p[1] for p in allp) / len(allp)
            xs = [p[0] for p in allp]; ys = [p[1] for p in allp]
            s = 1500.0 / max(max(xs) - min(xs), max(ys) - min(ys))
            def project(px, py, _cx=cx, _cy=cy, _s=s, _la=lat0, _ln=lng0, _R=R):
                return [_ln + (px - _cx) * _s / (111320 * _R),
                        _la + (py - _cy) * _s / 111320]
            meta = {"rotation_deg": 0, "scale": s, "fit_inside": None,
                    "method": "anchor-envelope"}
    # staged join first
    staged_hits = 0
    for (gid, num), pts in shapes.items():
        rec = feed_by_stage.get(shape_stage.get(gid, ""), {}).get(num)
        if rec:
            staged_hits += 1
    # renumber fallback: if no stage keys overlap at all, join bare numbers
    plan_stage_keys = {shape_stage.get(g, "") for g, _ in shapes} - {""}
    feed_stage_keys = set(feed_by_stage) - {""}
    use_bare = staged_hits == 0 and not (plan_stage_keys & feed_stage_keys)
    stage_remap = {}
    if use_bare:
        # size-order mapping: plan groups sorted by number paired to feed
        # stages sorted by number (renumbered generations, e.g. 1-6 -> 301-306)
        import re as _re
        def numkey(s):
            m = _re.search(r"(\d+)", s or "")
            return int(m.group(1)) if m else 10**9
        pg = sorted({g for g, _ in shapes}, key=lambda g: numkey(shape_stage.get(g, g)))
        fs = sorted(feed_stage_keys, key=numkey)
        if len(pg) == len(fs) and len(pg) > 1:
            for g, f in zip(pg, fs):
                stage_remap[shape_stage.get(g, "")] = f
            join_method = "stage-remap"
        else:
            join_method = "bare-renumber"
        bare_index = {}
        for l in lots:
            bare_index.setdefault(l.get("lot_number"), []).append(l)
    status_count = {}
    for (gid, num), pts in sorted(shapes.items()):
        if use_bare and stage_remap:
            fkey = stage_remap.get(shape_stage.get(gid, ""), "")
            rec = feed_by_stage.get(fkey, {}).get(num)
            # verify against bare ambiguity: skip if number exists in 2+ feed stages
            if rec is not None and len(bare_index.get(num, [])) > 1:
                # same number in several feed stages: only accept if this remap
                # stage is the unique... be strict: require uniqueness
                rec = None
        elif use_bare:
            cands = bare_index.get(num, [])
            rec = cands[0] if len(cands) == 1 else None
            if rec is None and len(cands) > 1:
                # ambiguous: keep unmatched
                pass
        else:
            rec = feed_by_stage.get(shape_stage.get(gid, ""), {}).get(num)
        m = rec is not None
        matched += m
        props = {"lot_number": num, "plan_stage": gid, "matched": m,
                 "kind": "lot polygon", "join_method": join_method if m else "none"}
        if m:
            props.update({"lot_id": str(rec["lot_id"]), "status": str(rec["lot_status"]),
                          "stage": rec.get("stage_name"),
                          "post_status": rec.get("lot_post_status")})
            status_count[rec["lot_status"]] = status_count.get(rec["lot_status"], 0) + 1
        ll = [project(x, y) for x, y in pts]
        ll.append(ll[0])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Polygon", "coordinates": [ll]},
                      "properties": props})
    use_ring = len(ring) >= 2 and (meta or {}).get("method") == "ring-centroid"
    if use_ring:
        feats.insert(0, {"type": "Feature",
                         "geometry": {"type": "Polygon", "coordinates":
                                     [[[c[1], c[0]] for c in ring] + [[ring[0][1], ring[0][0]]]]},
                         "properties": {"name": estate or slug, "kind": "estate boundary",
                                        "source": "peet mapConfig.mapCoordinates"}})
    else:
        # plan-envelope hull as the outline. (Parcel-fit estates skip the
        # mapConfig ring: it is decorative and can sit off the subdivision.)
        pts = [tuple(c) for f in feats if f["properties"].get("kind") == "lot polygon"
               for c in f["geometry"]["coordinates"][0]]
        hull = _convex_hull(pts)
        if len(hull) >= 3:
            feats.insert(0, {"type": "Feature",
                             "geometry": {"type": "Polygon",
                                          "coordinates": [hull + [hull[0]]]},
                             "properties": {"name": estate or slug,
                                            "kind": "estate boundary",
                                            "source": "plan envelope (convex hull of fitted lots)"}})
    meta = dict(meta or {})
    meta.update({"estate": slug, "polygons": len(feats) - 1,
                 "matched": matched, "status_matched": status_count,
                 "join_method": join_method,
                 "note": "lot footprints from for-sale SVG stage groups"})
    gj = {"type": "FeatureCollection", "features": feats, "metadata": meta}
    out = pathlib.Path(f"{OUT}/{slug}.smart.geojson")
    out.write_text(json.dumps(gj))
    return gj, meta


def render_preview(slug, gj, out=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    from matplotlib.collections import PatchCollection
    feats = gj["features"]
    ring = next((f for f in feats
                 if f["properties"].get("kind") == "estate boundary"), None)
    lots = [f for f in feats if f["properties"].get("kind") == "lot polygon"]
    lons = [c[0] for f in lots for c in f["geometry"]["coordinates"][0]]
    lats = [c[1] for f in lots for c in f["geometry"]["coordinates"][0]]
    clon, clat = sum(lons) / len(lons), sum(lats) / len(lats)
    R = math.cos(math.radians(clat))
    def xy(lon, lat):
        return ((lon - clon) * 111320 * R, (lat - clat) * 111320)
    COL = {"7": "#F15A29", "2": "#1f6f8b", "4": "#2a9d48", "5": "#7048b6",
           "1": "#8a94a6", "8": "#8a94a6", "3": "#8a94a6"}
    patches, cols = [], []
    for f in lots:
        pts = [xy(*c) for c in f["geometry"]["coordinates"][0]]
        patches.append(MplPoly(pts, closed=True))
        st = f["properties"].get("status")
        cols.append(COL.get(st, "#d7dde5") if f["properties"].get("matched")
                    else "#d7dde5")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), dpi=130)
    for ax, mode in zip(axes, ("status", "join")):
        if mode == "status":
            pc = PatchCollection(patches, facecolor=cols, edgecolor="white",
                                 linewidths=0.4)
            ax.set_title("abstract lot plan — live status fill")
        else:
            cols2 = ["#1f6f8b" if f["properties"].get("matched") else "#d7dde5"
                     for f in lots]
            pc = PatchCollection(
                [MplPoly([xy(*c) for c in f["geometry"]["coordinates"][0]],
                         closed=True) for f in lots],
                facecolor=cols2, edgecolor="white", linewidths=0.4)
            ax.set_title(f"join coverage — teal joins feed ({gj['metadata']['matched']})")
        ax.add_collection(pc)
        if ring:
            ox = [xy(*c)[0] for c in ring["geometry"]["coordinates"][0]]
            oy = [xy(*c)[1] for c in ring["geometry"]["coordinates"][0]]
            ax.plot(ox + [ox[0]], oy + [oy[0]], color="#1f6f8b", lw=1.6,
                    ls=(0, (5, 4)))
        else:
            ox = [xy(*c)[0] for f in lots for c in f["geometry"]["coordinates"][0]]
            oy = [xy(*c)[1] for f in lots for c in f["geometry"]["coordinates"][0]]
        ax.set_aspect("equal")
        ax.set_xlim(min(ox) - 40, max(ox) + 40)
        ax.set_ylim(min(oy) - 40, max(oy) + 40)
        ax.set_xlabel("metres")
    m = gj["metadata"]
    fig.suptitle(f"{slug} — {m['polygons']} lot polygons · {m['matched']} join "
                 f"live inventory [{m.get('method')}/{m.get('join_method')}]")
    fig.tight_layout()
    out = out or f"{OUT}/{slug}-smart-preview.png"
    fig.savefig(out)
    plt.close(fig)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="estate slugs or --all")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--fit-only", action="store_true",
                    help="print fit meta without writing")
    args = ap.parse_args()
    slugs = (sorted(os.path.basename(p).replace(".svg", "")
                     for p in glob.glob(f"{MAPS}/*.svg"))
             if args.all or not args.slugs else args.slugs)
    for slug in slugs:
        try:
            if args.fit_only:
                shapes, _ = parse_svg(slug)
                lots, ring, estate = load_feed(slug)
                if len(ring) >= 4:
                    _, meta = fit_ring(shapes, ring)
                elif pathlib.Path(f"{CAD}/{slug}.parcels.json").exists():
                    parcels, anchor = parcel_rings(slug)
                    _, meta = fit_parcels(shapes, residential(parcels), anchor)
                else:
                    meta = {"method": "anchor-envelope"}
                print(f"{slug:24} {meta}")
                continue
            gj, meta = build_one(slug)
            prev = render_preview(slug, gj) if not args.no_preview else "-"
            m = gj["metadata"]
            print(f"{slug:24} poly={m['polygons']:5} matched={m['matched']:4} "
                  f"{m.get('method')}/{m.get('join_method')} {prev}")
        except Exception as e:
            import traceback
            print(f"{slug:24} FAIL {e}")
            traceback.print_exc()



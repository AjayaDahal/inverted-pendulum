"""Print plates: the parts grouped onto shared Kobra S1 beds by material, so printing is a few jobs
instead of one file per part. Optional parts (the coupler for an optical encoder) sit on a plate
of their own.

Layout (from the VTOL project): each part keeps its print orientation (make_print_ready.py) and
only turns about Z. Its footprint is the convex hull of its print-ready mesh grown by its brim, laid
out on a 1 mm grid, GAP mm from every other footprint and MARGIN mm inside the bed. Parts go on largest first,
each at the lowest free spot, then the leftmost, trying its minimum-area orientation, that turned
90 deg, then the two diagonals; the finished layout is centred on the bed. Deterministic, so the
gate and the viewer recompute it. slice_all.py slices each plate with --arrange 0 and every copy
as its own object (cancellable on its own on the printer).
"""
import hashlib
import json
import os
from functools import lru_cache

import numpy as np

import geom as G
from make_print_ready import PARTS

PRINTER = "s1"
BED = 250.0
MARGIN = 10.0
GAP = 6.0
RES = 1.0

# In print order: the belt drive first (it fixes the belt), then the cart, then the pendulum.
PLATES = {
    "petg_1_belt_drive": [("motor_mount", 1), ("idler_mount", 1), ("clamp_jaw", 1), ("idler_slider", 2),
                          ("idler_sleeve", 1), ("rod_bumper", 4), ("cable_clip", 3)],
    "petg_2_pulleys_pivot": [("motor_pulley", 1), ("idler_pulley", 1), ("pulley_flange", 2), ("pendulum_hub", 1),
                             ("magnet_cap", 1)],
    "pla_1_carriage_plate": [("carriage_plate", 1)],
    "pla_2_bridge_clamp_tray": [("pivot_bridge", 1), ("belt_clamp", 1), ("electronics_tray", 1), ("switch_mount", 2),
                                ("as5600_mount", 1)],
    "pla_3_arm": [("pendulum_arm", 1), ("pendulum_tip", 1)],
    "petg_3_option_encoder": [("coupler", 1)],
}


def material(plate):
    mats = {PARTS[n]["material"] for n, _ in PLATES[plate]}
    if len(mats) != 1:
        raise ValueError(f"{plate}: mixed materials {mats}")
    return mats.pop()


def _hull(pts):
    """Convex hull, counter-clockwise (monotone chain)."""
    pts = np.unique(np.round(np.asarray(pts, float), 4), axis=0)
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) -
                                     (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]
    return np.array(half(pts) + half(pts[::-1]))


def _area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _rot(pts, deg):
    """Turn about z, rounded to 1e-6 mm: cos/sin and FMA differ in the last bit between platforms,
    and the layout must not (round parts have exactly tied orientations, e.g. 45 and 135 deg)."""
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.round(pts @ np.array([[c, s], [-s, c]]), 6)


@lru_cache(maxsize=None)
def _footprint(name):
    """Convex hull of the print-ready mesh seen from above, grown by the part's brim (so the GAP is
    kept from the brim's edge, and no brim reaches past the bed's MARGIN), and the angle that lays its
    minimum-area rectangle along the axes (long side along x); near-square parts stay square."""
    v = G.read_stl(os.path.join(G.PRINT, name + ".stl")).reshape(-1, 3)
    hull = _hull(v[:, :2])
    brim = PARTS[name]["brim"]
    if brim:
        a = np.radians(np.arange(0.0, 360.0, 15.0))
        ring = np.round(np.c_[np.cos(a), np.sin(a)] * brim, 6)
        hull = _hull((hull[:, None, :] + ring[None, :, :]).reshape(-1, 2))
    best = None
    for p, q in zip(hull, np.roll(hull, -1, axis=0)):
        ang = -np.degrees(np.arctan2(q[1] - p[1], q[0] - p[0]))
        r = _rot(hull, ang)
        w, h = r.max(0) - r.min(0)
        area = round(w * h, 6)
        if best is None or area < best[0]:
            best = (area, (ang + (90.0 if h > w else 0.0)) % 180.0)
    w0, h0 = hull.max(0) - hull.min(0)
    if w0 * h0 <= 1.02 * best[0]:
        return hull, 0.0 if w0 >= h0 else 90.0
    return hull, best[1]


def _inside(poly, cx, cy, grow=0.0):
    """Grid points within `grow` of the convex polygon (mitred corners: conservative)."""
    d = np.full(cx.shape, -np.inf)
    for p, q in zip(poly, np.roll(poly, -1, axis=0)):
        e = q - p
        n = np.array([e[1], -e[0]]) / np.hypot(*e)
        d = np.maximum(d, (cx - p[0]) * n[0] + (cy - p[1]) * n[1])
    return np.round(d, 9) <= grow     # rounded: a point exactly `grow` away counts the same on every platform


def placed_hull(name, x, y, angle):
    return _rot(_footprint(name)[0], angle) + (x, y)


def _to_edges(pts, poly):
    a, b = poly, np.roll(poly, -1, axis=0)
    ab = b - a
    keep = (ab * ab).sum(-1) > 1e-12
    a, ab = a[keep], ab[keep]
    t = np.clip(((pts[:, None, :] - a) * ab).sum(-1) / (ab * ab).sum(-1), 0.0, 1.0)
    return np.linalg.norm(pts[:, None, :] - (a + t[..., None] * ab), axis=-1).min(1)


def hull_gap(P, Q):
    """Shortest distance between two convex polygons; 0 if they touch or overlap."""
    for A, B in ((P, Q), (Q, P)):
        for p, q in zip(A, np.roll(A, -1, axis=0)):
            n = np.array([q[1] - p[1], p[0] - q[0]])
            if ((B - p) @ n).min() > 0:
                break
        else:
            continue
        break
    else:
        return 0.0
    return float(min(_to_edges(P, Q).min(), _to_edges(Q, P).min()))


def placed_mesh(name, x, y, angle):
    tris = G.read_stl(os.path.join(G.PRINT, name + ".stl"))
    return G.transform(tris, G.rotation("z", angle), (x, y, 0.0))


@lru_cache(maxsize=None)
def layout(plate):
    """Placements on the bed: (part, copy, x, y, angle), copy counting from 1."""
    return layout_items(tuple(PLATES[plate]), plate)


def footprint_area(name):
    return _area(_footprint(name)[0])


def fits(items):
    """Whether ((part, copies), ...) all go on one bed."""
    try:
        layout_items(tuple(items))
        return True
    except ValueError:
        return False


@lru_cache(maxsize=None)
def layout_items(items, plate="plate"):
    """layout() for any ((part, copies), ...)."""
    n = int(round(BED / RES))
    centres = (np.arange(n) + 0.5) * RES
    gx, gy = np.meshgrid(centres, centres)
    blocked = np.zeros((n, n), bool)
    size = 2 * n
    items_ = [(name, k) for name, copies in items for k in range(1, copies + 1)]
    area = {name: _area(_footprint(name)[0]) for name, _ in items}
    items_.sort(key=lambda it: (-area[it[0]], it[0], it[1]))
    placed = []
    for name, k in items_:
        hull, base = _footprint(name)
        best = None
        for pref, turn in enumerate((0.0, 90.0, 45.0, 135.0)):
            angle = round((base + turn) % 360.0, 6)
            poly = _rot(hull, angle)
            lo, hi = poly.min(0), poly.max(0)
            f0 = np.floor(lo / RES).astype(int)
            w, h = (np.ceil(hi / RES).astype(int) - f0)
            if w > n or h > n:
                continue
            lx, ly = np.meshgrid((np.arange(w) + 0.5 + f0[0]) * RES, (np.arange(h) + 0.5 + f0[1]) * RES)
            mask = _inside(poly, lx, ly).astype(float)
            overlap = np.fft.irfft2(np.fft.rfft2(blocked.astype(float), (size, size)) *
                                    np.conj(np.fft.rfft2(mask, (size, size))), (size, size))[:n, :n]
            ox, oy = np.meshgrid(np.arange(n), np.arange(n))
            tx, ty = (ox - f0[0]) * RES, (oy - f0[1]) * RES
            ok = (overlap < 0.5) & (lo[0] + tx >= MARGIN) & (hi[0] + tx <= BED - MARGIN) & \
                 (lo[1] + ty >= MARGIN) & (hi[1] + ty <= BED - MARGIN)
            if not ok.any():
                continue
            top = np.where(ok, hi[1] + ty, np.inf)
            j = np.lexsort((tx.ravel(), top.ravel()))[0]
            # compared rounded, so exact ties (symmetric parts) go to the preferred turn on every platform
            cand = (round(float(top.ravel()[j]), 4), pref, tx.ravel()[j], angle, tx.ravel()[j], ty.ravel()[j], poly)
            if best is None or cand[:3] < best[:3]:
                best = cand
        if best is None:
            raise ValueError(f"plate {plate}: no room for {name} copy {k}")
        _, _, _, angle, tx, ty, poly = best
        blocked |= _inside(poly + (tx, ty), gx, gy, GAP)
        placed.append((name, k, float(tx), float(ty), float(angle)))
    hulls = [placed_hull(name, x, y, a) for name, _, x, y, a in placed]
    lo, hi = np.min([p.min(0) for p in hulls], 0), np.max([p.max(0) for p in hulls], 0)
    sx, sy = (BED - lo - hi) / 2
    return tuple(sorted((name, k, round(x + sx, 3), round(y + sy, 3), a) for name, k, x, y, a in placed))


def stl_name(name, k, copies):
    """The file name a placed copy is sliced from: it names the object on the printer."""
    return f"{name}_{k}" if copies > 1 else name


def gcode_path(plate):
    return os.path.join(G.ROOT, "gcode", f"{PRINTER}_{material(plate)}_plates", plate + ".gcode")


def plate_hash(plate):
    """Hash of everything a plate's G-code depends on: each part's print-ready STL and its place."""
    h = hashlib.sha256()
    for name, k, x, y, a in layout(plate):
        with open(os.path.join(G.PRINT, name + ".stl"), "rb") as f:
            h.update(hashlib.sha256(f.read()).digest())
        h.update(json.dumps([name, k, x, y, a]).encode())
    return h.hexdigest()


if __name__ == "__main__":
    for plate in PLATES:
        lay = layout(plate)
        hulls = [placed_hull(n, x, y, a) for n, _, x, y, a in lay]
        lo, hi = np.min([p.min(0) for p in hulls], 0), np.max([p.max(0) for p in hulls], 0)
        gaps = [hull_gap(hulls[i], hulls[j]) for i in range(len(hulls)) for j in range(i + 1, len(hulls))]
        fill = sum(_area(h) for h in hulls) / BED ** 2
        print(f"{plate}: {len(lay)} prints, x {lo[0]:.1f}..{hi[0]:.1f}, y {lo[1]:.1f}..{hi[1]:.1f}, closest "
              f"{min(gaps) if gaps else float('nan'):.2f} mm apart, {100 * fill:.0f} % of the bed")
        for n, k, x, y, a in lay:
            print(f"   {n:18s} {k:2d}  x {x:6.1f}  y {y:6.1f}  turned {a:6.1f} deg")

"""Verification gate: run before printing anything (and on every push, in CI).

Rebuilds every part from the scripts and checks, with build123d solids and the committed files:
  parts      every printed part is a valid solid and its committed STLs match the scripts
  bed        every print file and plate fits the Kobra S1; every copy is on exactly one plate; a
             part taller than the square root of its first layer's area has a brim
  overhang   every print-ready part, cut into layers, prints without supports
  air        the G-code lays nothing far over air and no wall in mid-air (touching nothing)
  clash      no two parts overlap at the home pose (shaft and magnet cap at 4 angles too)
  travel     the cart sweeps its whole travel without touching the frame, motor, idler or belt
             (the SC8UU blocks meet the bumpers at the stops; the switches trip 4 mm before)
  pendulum   the hub, arm and tip sweep a full turn at every cart position: nothing in the way,
             the tip clears the desk
  belt       pulleys and clamp on one plane and one height; the jaw's seats in phase with the
             belt's teeth; the lower run clears the jaw; the tension range covers the belt
  bolts      every screw is long enough to engage its nut or thread and not much longer
  sim        from hanging still, the controller swings up, holds and takes a push on every
             robustness run (model error, delay 8-20 ms, pivot friction, upright error, AS5600
             or encoder), inside the soft limits, within the motor's force at speed less friction;
             balanced at the pivot's goal friction, its hunting stays small
  firmware   firmware/pendulum/config.h is current; controller.h, compiled, gives the simulated
             controller's commands on replayed runs, and its f test finds the pivot's friction
             on simulated free swings (needs a C++ compiler: CI has one)
  files      G-code and 3MF stamps match the current STLs, presets and brims are what the print
             table says, the complete project, the to-print project, tracker, BOM, manifest and
             sim.json are current
Usage: python check_parts.py [--no-gcode]
"""
import glob
import json
import math
import os
import sys
import time
import zipfile

import numpy as np
from build123d import Location

import assembly as A
import geom as G
import hardware as H
import params as P
import plates as PT
import structure as S
import vitamins as V
from make_print_ready import PARTS as PRINT

TOL_VOL = 2.5          # mm^3 of overlap counted as two faces touching (boolean fuzz), not a clash
RESULTS = []


def report(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
    if not ok and os.environ.get("GITHUB_ACTIONS") == "true":
        _annotate(f"gate {name}", detail)


def _annotate(title, text):
    """A GitHub Actions error annotation: shown on the run's page and readable without its log."""
    msg = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")[:3000]
    print(f"::error title={title}::{msg}", flush=True)


def bb(s):
    b = s.bounding_box()
    return np.array([b.min.X, b.min.Y, b.min.Z]), np.array([b.max.X, b.max.Y, b.max.Z])


def boxes_meet(a, b, tol=0.05):
    (a0, a1), (b0, b1) = a, b
    return bool(np.all(a0 <= b1 + tol) and np.all(b0 <= a1 + tol))


def overlap(a, b, ba=None, bb_=None):
    if not boxes_meet(ba or bb(a), bb_ or bb(b)):
        return 0.0
    try:
        return float((a & b).volume)
    except Exception:  # a failed boolean is reported as a clash, not ignored
        return float("nan")


def moved(s, x=0.0, M=None):
    if M is not None:
        return A._moved(s, M)
    return s.moved(Location((x, 0, 0))) if x else s


# ------------------------------------------------------------------ parts
def check_parts(parts):
    bad = []
    for name, s in parts.items():
        if not s.is_valid:
            bad.append(f"{name} invalid")
            continue
        path = os.path.join(G.ASSEMBLY, name + ".stl")
        if not os.path.exists(path):
            bad.append(f"{name}: no committed STL")
            continue
        tris = G.read_stl(path)
        vol = abs(G.signed_volume(tris))
        lo, hi = G.bounds(tris)
        b0, b1 = bb(s)
        if abs(vol - s.volume) > 0.005 * s.volume + 5 or np.abs(lo - b0).max() > 0.1 or np.abs(hi - b1).max() > 0.1:
            bad.append(f"{name}: committed STL is stale (volume {vol:.0f} vs {s.volume:.0f} mm3)")
    report("parts", not bad, "; ".join(bad) or f"{len(parts)} parts valid, committed STLs match the scripts")


# ------------------------------------------------------------------ bed
def first_layer_area(tris):
    """mm^2 of the print-ready part on the bed: its section in the first layer."""
    zr = np.stack([tris[..., 2].min(1), tris[..., 2].max(1)], 1)
    lo, hi = G.bounds(tris)
    nx, ny = int((hi[0] - lo[0] + 4) / PIX) + 1, int((hi[1] - lo[1] + 4) / PIX) + 1
    return float(_layer(tris, zr, LAYER / 2, lo[0] - 2, lo[1] - 2, nx, ny).sum()) * PIX * PIX


def check_bed():
    bad, tall = [], []
    for name in PRINT:
        path = os.path.join(G.PRINT, name + ".stl")
        if not os.path.exists(path):
            bad.append(f"{name}: no print-ready STL")
            continue
        tris = G.read_stl(path)
        lo, hi = G.bounds(tris)
        ext = hi - lo
        if abs(lo[2]) > 1e-6 or ext[0] > P.BED - 10 or ext[1] > P.BED - 10 or ext[2] > P.BED - 10:
            bad.append(f"{name}: {ext.round(1)} mm, z0 {lo[2]:.3f}")
        # taller than the side of a square of its first layer: a lever the nozzle can pry off the bed
        area = first_layer_area(tris)
        if ext[2] > math.sqrt(area):
            tall.append(name)
            if not PRINT[name]["brim"]:
                bad.append(f"{name}: {ext[2]:.0f} mm tall on {area:.0f} mm2 of first layer and no brim")
    count = {}
    for plate, items in PT.PLATES.items():
        try:
            PT.material(plate)
            lay = PT.layout(plate)
        except Exception as exc:
            bad.append(str(exc))
            continue
        for n, k, x, y, a in lay:
            count[n] = count.get(n, 0) + 1
            h = PT.placed_hull(n, x, y, a)
            if h.min() < PT.MARGIN - 0.6 or h.max() > PT.BED - PT.MARGIN + 0.6:
                bad.append(f"{plate}: {n} {k} off the bed")
    for n, spec in PRINT.items():
        if count.get(n, 0) != spec["qty"]:
            bad.append(f"{n}: {count.get(n, 0)} on plates, print table says {spec['qty']}")
    report("bed", not bad, "; ".join(bad) or f"{len(PRINT)} print files and {len(PT.PLATES)} plates fit; "
                                            f"every copy on exactly one plate; the {len(tall)} parts taller than "
                                            f"the square root of their first layer's area have a brim "
                                            f"({', '.join(sorted(tall))})")


# ------------------------------------------------------------------ overhang
LAYER, PIX = 0.2, 0.2
REACH = 0.6              # mm a layer may stand out over the one below (45 deg, plus a line's width)
CANTILEVER_MAX = 3.0     # mm a region may reach out held on one side
BRIDGE_MAX = 34.0        # mm a region may span between holds (a ceiling held all round spans twice its reach)


def _layer(tris, zr, z, x0, y0, nx, ny):
    """The part's cross-section at height z as a raster (even-odd fill of the cut outline)."""
    t = tris[(zr[:, 0] < z) & (zr[:, 1] > z)]
    img = np.zeros((ny, nx + 1), np.int32)
    if not len(t):
        return img[:, :nx] > 0
    a, b = t, np.roll(t, -1, axis=1)
    cross = (a[..., 2] > z) != (b[..., 2] > z)
    s = (z - a[..., 2]) / np.where(cross, b[..., 2] - a[..., 2], 1.0)
    pts = a[..., :2] + s[..., None] * (b[..., :2] - a[..., :2])
    order = np.argsort(~cross, axis=1, kind="stable")[:, :2]
    seg = np.take_along_axis(pts, order[..., None], axis=1)
    seg = seg[cross.sum(1) == 2]
    (px, py), (qx, qy) = seg[:, 0].T, seg[:, 1].T
    j0 = np.ceil((np.minimum(py, qy) - y0) / PIX - 0.5).astype(int)
    j1 = np.ceil((np.maximum(py, qy) - y0) / PIX - 0.5).astype(int)
    n = np.clip(j1 - j0, 0, None)
    k = np.repeat(np.arange(len(seg)), n)
    jj = j0[k] + np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    yc = y0 + (jj + 0.5) * PIX
    xc = px[k] + (yc - py[k]) * (qx[k] - px[k]) / (qy[k] - py[k])
    ii = np.clip(np.ceil((xc - x0) / PIX - 0.5).astype(int), 0, nx)
    ok = (jj >= 0) & (jj < ny)
    np.add.at(img, (jj[ok], ii[ok]), 1)
    return (np.cumsum(img, axis=1)[:, :nx] % 2) == 1


def overhangs(name):
    """Regions of the print-ready part with nothing under them, layer by layer: (kind, z, reach mm),
    kind 'island' (no hold), 'cantilever' (one), 'ceiling' (held all round) or 'bridge' (two or more)."""
    from scipy import ndimage as ndi
    tris = G.read_stl(os.path.join(G.PRINT, name + ".stl"))
    zr = np.stack([tris[..., 2].min(1), tris[..., 2].max(1)], 1)
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    x0, y0 = lo[0] - 2, lo[1] - 2
    nx, ny = int((hi[0] - lo[0] + 4) / PIX) + 1, int((hi[1] - lo[1] + 4) / PIX) + 1
    r = int(round(REACH / PIX))
    disk = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
    out, prev = [], None
    for k in range(int(hi[2] / LAYER)):
        z = (k + 0.5) * LAYER + 1e-4
        cur = _layer(tris, zr, z, x0, y0, nx, ny)
        if prev is not None and cur.any():
            over = cur & ~ndi.binary_dilation(prev, disk)
            if over.any():
                lab, n = ndi.label(over)
                dist = ndi.distance_transform_edt(~prev) * PIX
                for i in range(1, n + 1):
                    comp = lab == i
                    reach = float(dist[comp].max())
                    if comp.sum() * PIX * PIX < 0.5:
                        continue
                    holds = ndi.label(ndi.binary_dilation(comp, iterations=r + 2) & prev, np.ones((3, 3)))[1]
                    rim = ndi.binary_dilation(comp) & ~comp
                    held = (rim & ndi.binary_dilation(prev, disk)).sum() / max(rim.sum(), 1)
                    kind = ("island" if holds == 0 else "ceiling" if held > 0.9 else
                            "bridge" if holds > 1 else "cantilever")
                    out.append((kind, round(z, 1), round(reach, 1)))
        prev = cur
    return out


def check_overhang():
    bad, longest = [], (0.0, "")
    limit = {"island": 0.0, "cantilever": CANTILEVER_MAX, "ceiling": BRIDGE_MAX / 2, "bridge": BRIDGE_MAX / 2}
    for name in PRINT:
        for kind, z, reach in overhangs(name):
            if reach > limit[kind]:
                bad.append(f"{name}: {kind} reaching {reach} mm at z {z}")
            elif kind in ("bridge", "ceiling") and 2 * reach > longest[0]:
                longest = (2 * reach, name)
    report("overhang", not bad, "; ".join(bad[:8]) or
           f"{len(PRINT)} parts print without supports: no islands, nothing held on one side reaches past "
           f"{CANTILEVER_MAX:g} mm, bridges up to {longest[0]:.0f} mm ({longest[1]}; at most {BRIDGE_MAX:g})")


# ------------------------------------------------------------------ G-code over air
AIR_RES, AIR_HALF = 0.2, 0.225   # mm: map resolution; half a line's width
FREE_RUN, FREE_AIR = 1.0, 1.0    # mm: how far a wall laid in mid-air may run, or lie from the layer below
WALLS = ("Outer wall", "Inner wall", "Overhang wall")


def gcode_moves(path):
    """Extrusions of a G-code file: (n, 5) [layer z, x0, y0, x1, y1] in print order, and each one's
    feature type (relative E, as the Kobra S1's G-code is written; arcs are off)."""
    rows, kinds = [], []
    z, kind, x, y = 0.0, "", 0.0, 0.0
    with open(path, errors="replace") as f:
        for line in f:
            if line[0] == ";":
                if line.startswith(";Z:"):
                    z = float(line[3:])
                elif line.startswith(";TYPE:"):
                    kind = line[6:].strip()
                continue
            if line.startswith(("G2 ", "G3 ")):
                raise RuntimeError(f"{os.path.basename(path)}: arc moves (arc fitting must stay off)")
            if not line.startswith(("G1 ", "G0 ")):
                continue
            nx, ny, e = x, y, 0.0
            for tok in line.split(";", 1)[0].split()[1:]:
                if tok[0] == "X":
                    nx = float(tok[1:])
                elif tok[0] == "Y":
                    ny = float(tok[1:])
                elif tok[0] == "E":
                    e = float(tok[1:])
            if e > 0 and (nx != x or ny != y):
                rows.append((z, x, y, nx, ny))
                kinds.append(kind)
            x, y = nx, ny
    return np.array(rows, float).reshape(-1, 5), np.array(kinds)


def over_air(path):
    """Every stretch of a line in one G-code file whose bead overlaps nothing in the layer below:
    [(feature type, length, farthest from the layer below, ends anchored on material, z, laid in
    mid-air)]. Lines are sampled every AIR_RES mm against a map of the layer below. A wall is laid in
    mid-air where, besides nothing under it, no line of its own layer printed before its own path
    began lies beside it: so the thrust stand's crank laid its hole's walls over its bearing seat."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from scipy.spatial import cKDTree
    segs, kinds = gcode_moves(path)
    keep = kinds != "Custom"                 # the purge line, off the bed's front
    segs, kinds = segs[keep], kinds[keep]
    zs, layer = np.unique(np.round(segs[:, 0], 3), return_inverse=True)
    pts = np.concatenate([segs[:, 1:3], segs[:, 3:5]])
    lo = pts.min(0) - 1.0
    size = np.ceil((pts.max(0) + 1.0 - lo) / AIR_RES).astype(int) + 1
    out = []
    for li in range(1, len(zs)):             # the first layer lies on the bed
        img = Image.new("1", (int(size[0]), int(size[1])), 0)
        dr = ImageDraw.Draw(img)
        for _, x0, y0, x1, y1 in segs[layer == li - 1].tolist():
            dr.line(((x0 - lo[0]) / AIR_RES, (y0 - lo[1]) / AIR_RES, (x1 - lo[0]) / AIR_RES, (y1 - lo[1]) / AIR_RES),
                    fill=1, width=max(1, round(2 * AIR_HALF / AIR_RES)))
        air = ndimage.distance_transform_edt(~np.array(img, bool)) * AIR_RES
        cur, k = segs[layer == li], kinds[layer == li]
        ln = np.hypot(cur[:, 3] - cur[:, 1], cur[:, 4] - cur[:, 2])
        n = np.maximum(2, (ln / AIR_RES).astype(int) + 1)
        first = np.cumsum(n) - n
        idx = np.repeat(np.arange(len(cur)), n)
        t = (np.arange(n.sum()) - first[idx]) / (n - 1)[idx]
        px = cur[idx, 1] + (cur[idx, 3] - cur[idx, 1]) * t
        py = cur[idx, 2] + (cur[idx, 4] - cur[idx, 2]) * t
        d = air[np.clip(((py - lo[1]) / AIR_RES).astype(int), 0, air.shape[0] - 1),
                np.clip(((px - lo[0]) / AIR_RES).astype(int), 0, air.shape[1] - 1)]
        over = d > AIR_HALF
        if not over.any():
            continue
        # a path breaks where a line does not start where the previous one ended
        brk = np.ones(len(cur), bool)
        brk[1:] = np.hypot(cur[1:, 1] - cur[:-1, 3], cur[1:, 2] - cur[:-1, 4]) > 1e-3
        new_path = np.zeros(len(px), bool)
        new_path[first[brk]] = True
        arc = np.repeat(np.cumsum(ln) - ln, n) + t * ln[idx]
        alone = np.zeros(len(px), bool)
        cand = np.flatnonzero(over & np.isin(k[idx], WALLS))
        if len(cand):
            path0 = first[np.maximum.accumulate(np.where(brk, np.arange(len(cur)), 0))][idx]
            near = cKDTree(np.c_[px, py]).query_ball_point(np.c_[px[cand], py[cand]], r=2 * AIR_HALF + 0.05)
            alone[cand] = [min(nb) >= p0 for nb, p0 in zip(near, path0[cand])]
        for mask, free in ((over, False), (alone, True)):
            edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
            for a, b in zip(edges[::2], edges[1::2]):
                cuts = [a, *(np.flatnonzero(new_path[a + 1:b]) + a + 1).tolist(), b]
                for s0, s1 in zip(cuts, cuts[1:]):
                    ends = int(s0 > 0 and not new_path[s0] and not mask[s0 - 1]) + \
                        int(s1 < len(px) and not new_path[s1] and not mask[s1])
                    out.append((str(k[idx[s0]]), float(arc[s1 - 1] - arc[s0]), float(d[s0:s1].max()), ends,
                                float(zs[li]), free))
    return out


def check_air():
    """What each part's and each plate's G-code lays over air, against the layer below (a plate turns
    its parts and prints them together, so the slicer's lines differ a little from the part's own file):
    a line lying more than CANTILEVER_MAX from the layer below must span at most BRIDGE_MAX between
    two anchors, whatever the slicer calls it; and no wall is laid in mid-air, touching nothing as it
    prints, beyond a short run (FREE_RUN), a run close to the layer below (FREE_AIR), a stub held at
    one end no longer than CANTILEVER_MAX or a small bridge between two anchors. The raster check
    (overhang) cannot see the last: a ring of hole walls over a pocket is a short ledge there
    (REPORT.md, R1, R2)."""
    import slice_all as SA
    bad, span, ledge, freest, n = [], (0.0, ""), (0.0, ""), (0.0, ""), 0
    jobs = [(name, SA.out_path(name)) for name in sorted(PRINT)] + \
           [(f"plate {plate}", PT.gcode_path(plate)) for plate in PT.PLATES]
    for name, path in jobs:
        if not os.path.exists(path):
            continue                         # reported by check_files
        n += 1
        for kind, ln, d, ends, z, free in over_air(path):
            where = f"{name} at z {z:.1f}"
            if free:
                if ln > FREE_RUN and d > FREE_AIR and not (ends == 2 and ln <= BRIDGE_MAX) and \
                        not (ends == 1 and ln <= CANTILEVER_MAX):
                    bad.append((ln, f"{where}: a wall laid in mid-air for {ln:.1f} mm, {d:.1f} mm from the layer below, "
                                    f"anchored at {ends} of its ends"))
                elif ln > freest[0]:
                    freest = (ln, f"{where}, {d:.1f} mm out, anchored at {ends} ends")
            elif d > CANTILEVER_MAX:
                if ends < 2 or ln > BRIDGE_MAX:
                    bad.append((d, f"{where}: {kind} {d:.1f} mm out over air for {ln:.1f} mm, anchored at {ends} of its ends"))
                elif ln > span[0]:
                    span = (ln, f"{where}, {kind}")
            elif ends < 2 and d > ledge[0]:
                ledge = (d, f"{where}, {kind}")
    report("air", not bad, "; ".join(m for _, m in sorted(bad, reverse=True)[:8]) or
           f"{n} G-code files (parts and plates): spans over air up to {span[0]:.1f} mm ({span[1]}; at most {BRIDGE_MAX:g}), "
           f"lines held at one end or none up to {ledge[0]:.1f} mm out ({ledge[1]}; at most {CANTILEVER_MAX:g}); longest "
           f"wall laid in mid-air {freest[0]:.1f} mm ({freest[1]})")


# ------------------------------------------------------------------ clash at home
def all_solids(parts, vit, x=0.0, theta=0.0):
    return A.solids_at(x, theta, parts=parts, vit=vit)


def check_clash(parts, vit, belt_env):
    sol = all_solids(parts, vit)
    sol["belt_envelope"] = (belt_env, "belt")
    names = sorted(sol)
    boxes = {n: bb(sol[n][0]) for n in names}
    contact_ok = {("belt_envelope", "belt_clamp"), ("belt_envelope", "clamp_jaw"), ("belt_envelope", "motor_pulley"),
                  ("belt_envelope", "idler_pulley"), ("belt_envelope", "pulley_flange_1"),
                  ("belt_envelope", "pulley_flange_2")}
    clashes, pairs = [], 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not boxes_meet(boxes[a], boxes[b]):
                continue
            if (a, b) in contact_ok or (b, a) in contact_ok:
                continue
            pairs += 1
            v = overlap(sol[a][0], sol[b][0], boxes[a], boxes[b])
            if not v <= TOL_VOL:
                clashes.append(f"{a} x {b}: {v:.1f} mm3")
    # the parts that turn with the shaft, at four angles, against the cart
    cart = {n: s for n, (s, g) in sol.items() if g in ("cart",)}
    for th in (90.0, 180.0, 270.0):
        rot = all_solids(parts, vit, 0.0, th)
        for pn in ("pivot_shaft", "magnet", "magnet_cap", "pendulum_hub"):
            for cn, cs in cart.items():
                v = overlap(rot[pn][0], cs)
                if not v <= TOL_VOL:
                    clashes.append(f"{pn} at {th:.0f} deg x {cn}: {v:.1f} mm3")
    report("clash", not clashes, "; ".join(clashes) or f"{len(names)} solids, {pairs} close pairs, no overlap "
                                                      f"(> {TOL_VOL:g} mm3) at home; shaft parts clear at 4 angles")


# ------------------------------------------------------------------ travel
def check_travel(parts, vit, belt_env):
    home = all_solids(parts, vit)
    static = {n: s for n, (s, g) in home.items() if g in ("frame", "motor_pulley", "idler_pulley", "pulleys_m", "pulleys_i")
              and not n.startswith("endstop")}
    static["belt_envelope"] = belt_env
    cart = {n: s for n, (s, g) in home.items() if g == "cart"}
    sboxes = {n: bb(s) for n, s in static.items()}
    bad, gaps = [], []
    allowed = {("belt_clamp", "belt_envelope"), ("clamp_jaw", "belt_envelope")}
    for x in (-P.X_STOP, -P.X_SWITCH, -180.0, -120.0, -60.0, 0.0, 60.0, 120.0, 180.0, P.X_SWITCH, P.X_STOP):
        for cn, cs in cart.items():
            m = moved(cs, x)
            mb = bb(m)
            for sn, ss in static.items():
                if (cn, sn) in allowed:
                    continue
                v = overlap(m, ss, mb, sboxes[sn])
                if not v <= TOL_VOL:
                    bad.append(f"x={x:+.0f}: {cn} x {sn} {v:.1f} mm3")
    # stops: the SC8UU ends meet the bumpers exactly at X_STOP; the switch trips before
    sc_end = P.BEARING_X + P.SC8UU["l"] / 2
    stop_gap = P.X_BUMPER - (P.X_STOP + sc_end)
    import vitamins as Vv
    g = Vv.endstop_geometry(1)
    trip = g["x_tip"] - P.PLATE_X
    if abs(stop_gap) > 1e-6:
        bad.append(f"SC8UU stops {stop_gap:.2f} mm from the bumpers at X_STOP")
    if P.X_BUMPER + P.BUMPER_W > P.X_SK8_IN + 1e-6:
        bad.append(f"bumpers reach into the SK8s ({P.X_BUMPER + P.BUMPER_W:.1f} > {P.X_SK8_IN:.1f})")
    if not (P.X_SOFT < trip < P.X_STOP - 2.0):
        bad.append(f"switch trips at {trip:.1f}, soft limit {P.X_SOFT}, stop {P.X_STOP}")
    # the switch body must stay outboard of the plate at the stop
    if g["x_body"][0] <= P.X_STOP + P.PLATE_X:
        bad.append("switch body inside the plate's stop position")
    gaps.append(f"travel +-{P.X_STOP:.0f} mm ({2 * P.X_STOP:.0f} total), switches trip at +-{trip:.0f}, "
                f"soft limit +-{P.X_SOFT:.0f}")
    report("travel", not bad, "; ".join(bad) or "; ".join(gaps) + "; cart clear of the frame, motor, idler and belt")


# ------------------------------------------------------------------ pendulum sweep
def check_pendulum(parts, vit):
    from cad import slot_y
    home = all_solids(parts, vit)
    others = {n: s for n, (s, g) in home.items() if g not in ("pendulum",)}
    obox = {n: bb(s) for n, s in others.items()}
    bad, info = [], []
    for pn in ("pendulum_hub", "pendulum_arm", "pendulum_tip"):
        tris = G.read_stl(os.path.join(G.ASSEMBLY, pn + ".stl"))
        v = tris.reshape(-1, 3)
        r = float(np.sqrt(v[:, 0] ** 2 + (v[:, 2] - P.Z_SHAFT) ** 2).max())
        y0, y1 = float(v[:, 1].min()), float(v[:, 1].max())
        env = slot_y(r, -P.X_STOP, P.Z_SHAFT, P.X_STOP, P.Z_SHAFT, y0, y1)
        eb = bb(env)
        for n, s in others.items():
            vv = overlap(env, s, eb, obox[n])
            if not vv <= TOL_VOL:
                bad.append(f"{pn} sweep x {n}: {vv:.1f} mm3")
        info.append(f"{pn} r {r:.0f} y {y0:.0f}..{y1:.0f}")
        if pn == "pendulum_tip" and P.Z_SHAFT - r < 15.0:
            bad.append(f"tip only {P.Z_SHAFT - r:.1f} mm above the desk")
    report("pendulum", not bad, "; ".join(bad) or "full turn clear at every cart position (" + ", ".join(info) +
           f"); tip {P.Z_SHAFT - P.ARM_L - P.TIP['wall']:.0f} mm above the desk when hanging")


# ------------------------------------------------------------------ belt geometry
def check_belt(parts):
    bad, info = [], []
    for name in ("motor_pulley", "idler_pulley"):
        M = S.PARTS[name]["copies"][0]
        s = moved(parts[name], M=M)
        b0, b1 = bb(s)
        mid = (b0[1] + b1[1]) / 2
        top = b1[2]
        if abs(mid - P.Y_BELT) > 0.01:
            bad.append(f"{name} mid-plane at y {mid:.2f}")
        if abs(M[:3, :3] @ np.array([0, 0, 1.0]) - np.array([0, -1.0, 0])).max() > 1e-9:
            bad.append(f"{name} axis not along y")
        info.append(f"{name} centre z {(b0[2] + b1[2]) / 2:.2f}")
    _, z_side, z_jaw0 = S._clamp_levels()
    jaw = parts["clamp_jaw"]
    jb0, jb1 = bb(jaw)
    if abs(jb1[2] - P.Z_RUN_LAND) > 0.01:
        bad.append(f"jaw lands at {jb1[2]:.2f}, belt land at {P.Z_RUN_LAND:.2f}")
    clamp_ceiling = P.Z_RUN_BACK
    if abs((clamp_ceiling - P.Z_RUN_LAND) - (P.BELT["thick"] - P.BELT["tooth_h"])) > 1e-6:
        bad.append("clamp gap is not the belt's back thickness")
    # seats in phase with the belt's teeth: a tooth centred on x = 0 on the upper run
    pts, nrm, s, total = V.belt_path()
    pitch_n = total / P.BELT["pitch"]
    info.append(f"loop {P.BELT_LOOP:.0f} mm at the nominal idler ({pitch_n:.1f} pitches of land line)")
    low_run_tips = P.Z_LOW_LAND + P.BELT["tooth_h"]
    head = P.HEAD["M3"][1]
    gap = (z_jaw0 - head) - low_run_tips
    if gap < 15.0:
        bad.append(f"lower run only {gap:.1f} mm under the jaw's screw heads")
    if not (P.IDLER_TRAVEL[0] < P.X_IDLER < P.IDLER_TRAVEL[1]):
        bad.append("nominal idler outside its travel")
    # the closed loop sets the pulleys' spacing: both must stay within the end frames
    if -P.X_MOTOR > P.X_END + 1e-6 or P.IDLER_TRAVEL[1] > P.X_END + 12.0:
        bad.append(f"a {P.BELT_TEETH}-tooth loop ({P.BELT_LOOP:.0f} mm) puts the pulleys {2 * P.X_IDLER:.0f} mm apart: "
                   f"outside the end frames ({2 * P.X_END:.0f}); cut it into an open belt")
    info.append(f"closed loop of {P.BELT_TEETH} teeth ({P.BELT_LOOP:.0f} mm): axles {P.C_NOM:.0f} mm apart")
    flange_room = (P.TOOTH_W - P.BELT["width"]) / 2
    if flange_room < 0.5:
        bad.append("belt rubs the flanges")
    report("belt", not bad, "; ".join(bad) or
           f"both pulleys on y = {P.Y_BELT:g} with axes along y, upper runs level at z {P.Z_RUN_LAND:.2f} = jaw lands; "
           f"lower run {gap:.0f} mm under the jaw; {flange_room:g} mm each side of the belt to the flanges; "
           f"tension range fits a closed loop of {P.BELT_LOOP_RANGE[0]:.0f}-{P.BELT_LOOP_RANGE[1]:.0f} mm; "
           + "; ".join(info))


# ------------------------------------------------------------------ bolts
ENGAGE_MIN = {"M3": 3.0, "M4": 4.0, "M5": 4.0}


def check_bolts():
    bad = []
    bl = H.bolts()
    for b in bl:
        nut_t = P.NUT[b["size"]][1]
        if b["nut"]:
            need, slack = b["stack"] + nut_t, 6.0 + nut_t
        elif b["tnut"]:
            need, slack = b["stack"] + 2.5, 6.0
        else:
            need, slack = b["stack"] + ENGAGE_MIN[b["size"]], 10.0
        if b["length"] < need - 0.3:
            bad.append(f"{b['name']} {b['size']}x{b['length']:.0f} short: needs {need:.1f}")
        elif b["length"] > need + slack:
            bad.append(f"{b['name']} {b['size']}x{b['length']:.0f} long for a {b['stack']:.1f} mm stack")
    report("bolts", not bad, "; ".join(bad) or f"{len(bl)} fasteners: every one engages and none sticks far out "
                                               f"({', '.join(f'{v} x {k}' for k, v in H.counts(bl).items())})")


# ------------------------------------------------------------------ sim
def check_sim():
    import sim
    res = sim.run(write=False, verbose=False)
    r = res["robust"]
    bad = []
    if not r["all_ok"]:
        bad.append(f"fails {len(r['fails'])} of {r['runs']} runs (plant, corner): {r['fails'][:8]}")
    if r["x_max_m"] > P.X_SOFT / 1000.0 - sim.X_MARGIN:
        bad.append(f"cart runs to {r['x_max_m'] * 1000:.0f} mm, soft limit {P.X_SOFT:.0f}")
    if r["force_margin_N"] < 0.0:
        bad.append(f"needs {-r['force_margin_N']:.2f} N more than the motor gives at {P.DRIVE['i_set']} A, "
                   f"{P.DRIVE['volts']:.0f} V, with {res['limits']['friction_N']} N of friction")
    if r["v_max_m_s"] > P.V_MAX or r["step_rate_hz"] > P.STEP_RATE_MAX:
        bad.append(f"speed {r['v_max_m_s']:.2f} m/s, {r['step_rate_hz']} steps/s")
    hunt = res["hunting"]
    goal = hunt["at_goal"]
    if (goal["theta_pp_deg"] > sim.HUNT_LIMIT["theta_pp_deg"] or goal["cart_pp_mm"] > sim.HUNT_LIMIT["cart_pp_mm"]
            or not all(row["balanced"] for row in hunt["table"])):
        bad.append(f"balanced at the pivot's goal ({goal['pivot_mNm']} mN m) it hunts {goal['theta_pp_deg']} deg and "
                   f"{goal['cart_pp_mm']} mm peak to peak (at most {sim.HUNT_LIMIT['theta_pp_deg']} and "
                   f"{sim.HUNT_LIMIT['cart_pp_mm']}), or falls at some friction up to {P.PIVOT_FRICTION * 1000:g}")
    path = os.path.join(G.PARTS_DIR, "sim.json")
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
        k_old, k_new = np.array(old.get("lqr_K", [0] * 5)), np.array(res["lqr_K"])
        g_old = old.get("hunting", {}).get("at_goal", {})
        if (k_old.shape != k_new.shape or np.abs(k_old - k_new).max() > 0.02 or "firmware" not in old
                or g_old.get("pivot_mNm") != goal["pivot_mNm"]
                or abs(g_old.get("theta_pp_deg", -9) - goal["theta_pp_deg"]) > 0.1
                or abs(g_old.get("cart_pp_mm", -99) - goal["cart_pp_mm"]) > 2.0
                or abs((old.get("swing_up_s") or 0) - (res["swing_up_s"] or 0)) > 0.1):
            bad.append("parts/sim.json is stale: run sim.py")
    else:
        bad.append("no parts/sim.json")
    lim = res["limits"]
    report("sim", not bad, "; ".join(bad) or
           f"from hanging still: kicked, caught at {res['swing_up_s']} s (worst {r['swing_up_s']} s), holds and takes a "
           f"{res['push_rad_s']:g} rad/s push on all {r['runs']} runs ({len(sim.PLANTS)} model variants x "
           f"{len(sim.CORNERS)} corners, and random ones: delay {P.ACT_DELAY[0] * 1000:.0f}-"
           f"{P.ACT_DELAY[1] * 1000:.0f} ms, pivot friction 0-{P.PIVOT_FRICTION * 1000:g} mN m, upright error "
           f"+-{P.ANGLE_OFFSET:g} deg, AS5600 or encoder); cart within +-{r['x_max_m'] * 1000:.0f} mm of "
           f"+-{P.X_SOFT:.0f}; force margin {r['force_margin_N']:.2f} N ({P.DRIVE['i_set']} A, "
           f"{P.DRIVE['volts']:.0f} V, friction {lim['friction_N']} N, a_max {lim['a_max']} m/s^2); balanced, it hunts "
           f"{goal['theta_pp_deg']} deg / {goal['cart_pp_mm']} mm peak to peak at the pivot's goal "
           f"{goal['pivot_mNm']} mN m ({hunt['deg_per_mNm']} deg / {hunt['mm_per_mNm']} mm per mN m); "
           f"K = {res['lqr_K']}")


# ------------------------------------------------------------------ firmware
def check_firmware():
    import make_firmware as MF
    bad = []
    if MF.render() != MF.current():
        bad.append("firmware/pendulum/config.h is stale: run make_firmware.py")
    status, detail = MF.controller_test()
    if status == "fail":
        bad.append("controller.h: " + detail)
    report("firmware", not bad, "; ".join(bad) or "config.h current; " + detail)


# ------------------------------------------------------------------ files
def check_files(no_gcode):
    import slice_all as SA
    bad, n = [], 0
    if not no_gcode:
        names = {"pla": SA.preset_names("pla"), "petg": SA.preset_names("petg")}
        jobs = [(SA.out_path(nm), SA.stl_hash(nm), PRINT[nm]["material"], {nm: PRINT[nm]["brim"]}) for nm in PRINT]
        jobs += [(PT.gcode_path(p), PT.plate_hash(p), PT.material(p),
                  {PT.stl_name(nm, k, dict(PT.PLATES[p])[nm]): PRINT[nm]["brim"] for nm, k, *_ in PT.layout(p)})
                 for p in PT.PLATES]
        for path, stamp, mat, brims in jobs:
            g, mins, st = SA.stats(path)
            rel = os.path.relpath(path, G.ROOT)
            if st != stamp:
                bad.append(f"{rel}: {'missing' if g is None else 'stale'}")
                continue
            with open(path, errors="replace") as f:
                head = f.read(400_000)
                f.seek(max(0, os.path.getsize(path) - 600_000))
                tail = f.read()
            text = head + tail
            for key, want in (("printer_settings_id", names[mat][0]), ("print_settings_id", names[mat][1]),
                              ("filament_type", mat.upper()), ("enable_support", "0")):
                if f"; {key} = {want}" not in text and f'; {key} = "{want}"' not in text:
                    bad.append(f"{rel}: {key} is not {want}")
            p3 = SA.path_3mf(path)
            if not os.path.exists(p3):
                bad.append(f"{os.path.relpath(p3, G.ROOT)} missing")
            else:
                with zipfile.ZipFile(p3) as z:
                    model = z.read("3D/3dmodel.model").decode(errors="replace")
                    ms = z.read("Metadata/model_settings.config").decode(errors="replace")
                if stamp not in model:
                    bad.append(f"{os.path.relpath(p3, G.ROOT)}: stamp missing")
                for obj, brim in brims.items():
                    has = f'<metadata key="name" value="{obj}.stl"/>' in ms
                    with_brim = has and f'value="{obj}.stl"/>' in ms and \
                        ms.split(f'value="{obj}.stl"/>', 1)[1].split("</object>", 1)[0].count('key="brim_width"') == 1
                    if bool(brim) != with_brim:
                        bad.append(f"{os.path.relpath(p3, G.ROOT)}: {obj} brim {'missing' if brim else 'unexpected'}")
            n += 1
        gc, tm = SA.expected_files()
        for keep, pattern in ((gc, ("gcode", "*", "*.gcode")), (tm, ("3mf", "*", "*.3mf"))):
            for path in glob.glob(os.path.join(G.ROOT, *pattern)):
                if os.path.normcase(os.path.abspath(path)) not in keep:
                    bad.append(f"stray {os.path.relpath(path, G.ROOT)}")
        try:
            import make_projects as MP
            bad += MP.stale()
        except Exception as exc:
            bad.append(f"complete project: {exc}")
        try:
            import make_to_print as MTP
            bad += MTP.stale()
            projects = {os.path.normcase(os.path.abspath(p)) for p in (MP.PATH, MTP.PATH)}
            for path in glob.glob(os.path.join(G.ROOT, "3mf", "*.3mf")):
                if os.path.normcase(os.path.abspath(path)) not in projects:
                    bad.append(f"stray {os.path.relpath(path, G.ROOT)}")
        except Exception as exc:
            bad.append(f"to-print project: {exc}")
    try:
        import make_tracker as MT
        if MT.render() != MT.current():
            bad.append("tracker.md is stale: run make_tracker.py")
    except Exception as exc:
        bad.append(f"tracker: {exc}")
    try:
        import make_bom as MB
        if MB.render() != MB.current():
            bad.append("BOM.md is stale: run make_bom.py")
    except Exception as exc:
        bad.append(f"BOM: {exc}")
    try:
        import make_viewer as MV
        if MV.render() != MV.current():
            bad.append("viewer/manifest.json is stale: run make_viewer.py")
    except Exception as exc:
        bad.append(f"viewer manifest: {exc}")
    report("files", not bad, "; ".join(bad[:12]) + (f" (+{len(bad) - 12} more)" if len(bad) > 12 else "") or
           ("G-code checks skipped (--no-gcode); " if no_gcode else f"{n} G-code jobs and their 3MFs current; the "
                                                                    f"complete and to-print projects current; ")
           + "tracker.md, BOM.md and viewer/manifest.json current")


def main():
    t0 = time.time()
    no_gcode = "--no-gcode" in sys.argv
    parts = S.build(write=False, verbose=False)
    vit = V.items(belt=False)
    belt_env = A.smooth_belt()
    check_parts(parts)
    check_bed()
    check_overhang()
    if not no_gcode:
        check_air()
    check_clash(parts, vit, belt_env)
    check_travel(parts, vit, belt_env)
    check_pendulum(parts, vit)
    check_belt(parts)
    check_bolts()
    check_sim()
    check_firmware()
    check_files(no_gcode)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks pass ({time.time() - t0:.0f} s)"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        if os.environ.get("GITHUB_ACTIONS") == "true":
            _annotate("gate crashed", traceback.format_exc())
        raise

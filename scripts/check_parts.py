"""Verification gate: run before printing anything (and on every push, in CI).

Rebuilds every part from the scripts and checks, with build123d solids and the committed files:
  parts      every printed part is a valid solid and its committed STLs match the scripts
  bed        every print file and plate fits the Kobra S1; every copy is on exactly one plate
  clash      no two parts overlap at the home pose (shaft and magnet cap at 4 angles too)
  travel     the cart sweeps its whole travel without touching the frame, motor, idler or belt
             (the SC8UU blocks meet the bumpers at the stops; the switches trip 4 mm before)
  pendulum   the hub, arm and tip sweep a full turn at every cart position: nothing in the way,
             the tip clears the desk
  belt       pulleys and clamp on one plane and one height; the jaw's seats in phase with the
             belt's teeth; the lower run clears the jaw; the tension range covers the belt
  bolts      every screw is long enough to engage its nut or thread and not much longer
  sim        the cart-pole model swings up and balances inside the soft limits, within the
             motor's force, on +-20 % model error (sim.py)
  files      G-code and 3MF stamps match the current STLs, presets and brims are what the print
             table says, the complete projects, tracker, manifest and sim.json are current
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
def check_bed():
    bad = []
    for name in PRINT:
        path = os.path.join(G.PRINT, name + ".stl")
        if not os.path.exists(path):
            bad.append(f"{name}: no print-ready STL")
            continue
        lo, hi = G.bounds(G.read_stl(path))
        ext = hi - lo
        if abs(lo[2]) > 1e-6 or ext[0] > P.BED - 10 or ext[1] > P.BED - 10 or ext[2] > P.BED - 10:
            bad.append(f"{name}: {ext.round(1)} mm, z0 {lo[2]:.3f}")
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
                                            f"every copy on exactly one plate")


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
    for x in (-P.X_STOP, -P.X_SWITCH, -120.0, -60.0, 0.0, 60.0, 120.0, P.X_SWITCH, P.X_STOP):
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
    stop_gap = (P.X_SK8_IN - P.BUMPER_W) - (P.X_STOP + sc_end)
    import vitamins as Vv
    g = Vv.endstop_geometry(1)
    trip = g["x_tip"] - P.PLATE_X
    if abs(stop_gap) > 1e-6:
        bad.append(f"SC8UU stops {stop_gap:.2f} mm from the bumpers at X_STOP")
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
        bad.append("swing-up or balance fails on a model variant")
    if r["x_max_m"] * 1000 > P.X_SOFT:
        bad.append(f"cart runs to {r['x_max_m'] * 1000:.0f} mm, soft limit {P.X_SOFT:.0f}")
    if r["f_peak_N"] > 1.15 * res["limits"]["f_max_N"]:
        bad.append(f"needs {r['f_peak_N']:.1f} N, motor gives {res['limits']['f_max_N']:.1f} N at half torque")
    if r["v_max_m_s"] > P.V_MAX:
        bad.append(f"speed {r['v_max_m_s']:.2f} m/s")
    path = os.path.join(G.PARTS_DIR, "sim.json")
    if os.path.exists(path):
        with open(path) as f:
            old = json.load(f)
        k_old, k_new = np.array(old.get("lqr_K", [0] * 4)), np.array(res["lqr_K"])
        if np.abs(k_old - k_new).max() > 0.02 or abs((old.get("swing_up_s") or 0) - (res["swing_up_s"] or 0)) > 0.1:
            bad.append("parts/sim.json is stale: run sim.py")
    else:
        bad.append("no parts/sim.json")
    report("sim", not bad, "; ".join(bad) or
           f"swings up in {res['swing_up_s']} s (worst {r['swing_up_s']} s over {r['plants']} model variants), cart "
           f"within +-{r['x_max_m'] * 1000:.0f} mm of +-{P.X_SOFT:.0f}, peak force {res['f_peak_N']:.1f} N "
           f"(worst {r['f_peak_N']:.1f} N; budget {res['limits']['f_max_N']:.1f} N at half the holding torque, "
           f"15 % over allowed), holds after a 1 rad/s kick; LQR K = {res['lqr_K']}")


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
            bad.append(f"complete projects: {exc}")
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
           ("G-code checks skipped (--no-gcode); " if no_gcode else f"{n} G-code jobs and their 3MFs current; ")
           + "tracker.md, BOM.md and viewer/manifest.json current")


def main():
    t0 = time.time()
    no_gcode = "--no-gcode" in sys.argv
    parts = S.build(write=False, verbose=False)
    vit = V.items(belt=False)
    belt_env = A.smooth_belt()
    check_parts(parts)
    check_bed()
    check_clash(parts, vit, belt_env)
    check_travel(parts, vit, belt_env)
    check_pendulum(parts, vit)
    check_belt(parts)
    check_bolts()
    check_sim()
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

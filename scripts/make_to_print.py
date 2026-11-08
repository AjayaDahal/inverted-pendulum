"""One slicer project with only the parts still to print: 3mf/to_print_kobra_s1.3mf.

The complete projects (make_projects.py) print every part, one project per material. The owner
reuses parts he already has, so this one leaves out what he keeps (HAVE), takes one angle
sensor's parts (SENSOR), and packs the rest onto as few beds as fit, one material per bed, in
print order (belt drive first, pendulum last), all in ONE project with two filaments: 1 = PLA,
2 = PETG. Each bed prints with its own filament's preset (temperatures, cooling); the process is
the PLA one, and every PETG object carries what the PETG process changes (its infill). Parts that
may not be needed (MAYBE) go on beds of their own, named so: print those only if you need them.

Edit HAVE, MAYBE and SENSOR below, then run: python scripts/make_to_print.py [--verify]
--verify slices every bed of the project (plate names blanked: the CLI crashes on them) and the
same bed again on its own with its material's own presets: both must give the same grams and the
same bed and nozzle temperatures.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import geom as G
import make_projects as MP
import plates as PT
import slice_all as SA
from make_print_ready import PARTS

PATH = os.path.join(G.ROOT, "3mf", "to_print_kobra_s1.3mf")

SENSOR = "as5600"                       # or "encoder": the coupler instead of the magnet cap and AS5600 adapter
SENSOR_PARTS = {"as5600": ("magnet_cap", "as5600_mount"), "encoder": ("coupler",)}
HAVE = {}                               # parts already printed and kept, with how many: e.g. {"pendulum_arm": 1}
# The owner's own idler pulley (20-tooth 8M, two flanges; photos of 2026-11-08) can replace these if
# it measures at most 25.5 mm over its flanges and its bore is drilled out to 8.5 mm for the sleeve.
MAYBE = {"idler_pulley": 1, "pulley_flange": 1}
MAYBE_WHY = "only if your own idler pulley does not fit"
FIL = {"pla": 1, "petg": 2}             # the project's filament slots


def _profile(name):
    with open(os.path.join(SA.PROFILES, name)) as f:
        return json.load(f)


def petg_overrides():
    """What the PETG process changes against the PLA one: set on each PETG object."""
    pla, petg = _profile(SA.PROCESS[("s1", "pla")]), _profile(SA.PROCESS[("s1", "petg")])
    return {k: v for k, v in petg.items() if k != "name" and pla.get(k) != v}


def wanted():
    """([(part, copies)] to print, [(part, copies)] that may be needed)."""
    drop = {p for s, ps in SENSOR_PARTS.items() if s != SENSOR for p in ps}
    need, maybe = [], []
    for name, spec in PARTS.items():
        if name in drop:
            continue
        n = max(spec["qty"] - HAVE.get(name, 0), 0)
        m = min(MAYBE.get(name, 0), n)
        if n - m:
            need.append((name, n - m))
        if m:
            maybe.append((name, m))
    return need, maybe


def _rank(name):
    """Print order of the complete plates (belt drive first), then the part's place on its plate."""
    for i, (plate, items) in enumerate(PT.PLATES.items()):
        for j, (n, _) in enumerate(items):
            if n == name:
                return i, j
    return len(PT.PLATES), 0


def pack(items):
    """First fit, largest footprint first, one material per bed: [(material, ((part, copies), ...))]."""
    beds = []
    for name, copies in sorted(items, key=lambda it: (-PT.footprint_area(it[0]), it[0])):
        mat, left = PARTS[name]["material"], copies
        for bed in beds:
            if bed[0] != mat or not left:
                continue
            k = left
            while k and not PT.fits(tuple(bed[1]) + ((name, k),)):
                k -= 1
            if k:
                bed[1].append((name, k))
                left -= k
        while left:
            k = left
            while k and not PT.fits(((name, k),)):
                k -= 1
            if not k:
                raise ValueError(f"{name} does not fit on an empty bed")
            beds.append([mat, [(name, k)]])
            left -= k
    beds = [(mat, tuple(sorted(its, key=lambda it: _rank(it[0])))) for mat, its in beds]
    return sorted(beds, key=lambda b: (min(_rank(n) for n, _ in b[1]), b[0]))


def plan():
    """[(label, material, items, maybe)] in print order."""
    need, maybe = wanted()
    out = []
    for group, opt in ((need, False), (maybe, True)):
        for mat, items in pack(group):
            n = sum(c for _, c in items)
            names = [nm if c == 1 else f"{c} x {nm}" for nm, c in items]
            text = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")
            label = f"{len(out) + 1} {mat.upper()} - {text} ({n} part{'s' * (n > 1)})"
            out.append((label + (f" - OPTION, {MAYBE_WHY}" if opt else ""), mat, items, opt))
    return out


def stamp(beds=None):
    """Hash of the presets (parsed, so line endings do not count), the beds and their layouts."""
    h = hashlib.sha256()
    for f in (SA.MACHINE["s1"], SA.PROCESS[("s1", "pla")], SA.PROCESS[("s1", "petg")], SA.FILAMENT["pla"],
              SA.FILAMENT["petg"]):
        h.update(json.dumps(_profile(f), sort_keys=True).encode())
    for label, mat, items, _ in beds or plan():
        h.update(json.dumps([label, mat]).encode())
        for name, k, x, y, a in PT.layout_items(items, label):
            h.update(SA.stl_hash(name).encode())
            h.update(json.dumps([name, k, x, y, a]).encode())
    return h.hexdigest()


def _bed_files(items, label, tmp):
    """Each copy's STL where it prints on the bed, and its own slicer settings."""
    copies = dict(items)
    stls, mats, own = [], [], {}
    for name, k, x, y, a in PT.layout_items(items, label):
        obj = PT.stl_name(name, k, copies[name]) + ".stl"
        path = os.path.join(tmp, obj)
        G.write_stl(path, PT.placed_mesh(name, x, y, a))
        stls.append(path)
        mats.append(PARTS[name]["material"])
        if SA.object_settings(name):
            own[obj] = SA.object_settings(name)
    return stls, mats, own


def _export(stls, process, filaments, ids, own, dst, tmp):
    name3 = os.path.basename(dst)
    cmd = [SA.SLICER, "--arrange", "0", "--orient", "0", "--ensure-on-bed", "--datadir", os.path.join(tmp, "cfg"),
           "--load-settings", ";".join([os.path.join(SA.PROFILES, SA.MACHINE["s1"]), os.path.join(SA.PROFILES, process)]),
           "--load-filaments", ";".join(os.path.join(SA.PROFILES, f) for f in filaments)]
    if ids:
        cmd += ["--load-filament-ids", ",".join(ids)]
    _, log = SA._run(cmd + ["--export-3mf", name3, "--outputdir", tmp, *stls], f"{name3}: no 3MF written")
    made = os.path.join(tmp, name3)
    if not os.path.exists(made):
        raise RuntimeError(log)
    if own:
        SA._set_object_settings(made, own)
    shutil.move(made, dst)


def bed_3mf(items, label, dst):
    """One bed as a two-filament project: PLA objects on filament 1, PETG on 2 with the PETG process's changes."""
    over = petg_overrides()
    with tempfile.TemporaryDirectory() as tmp:
        stls, mats, own = _bed_files(items, label, tmp)
        for path, mat in zip(stls, mats):
            if mat == "petg":
                obj = os.path.basename(path)
                own[obj] = {**over, **own.get(obj, {})}
        _export(stls, SA.PROCESS[("s1", "pla")], [SA.FILAMENT["pla"], SA.FILAMENT["petg"]],
                [str(FIL[m]) for m in mats], own, dst, tmp)


def _slice(project, plate, out):
    os.makedirs(out)
    run = subprocess.run([SA.SLICER, "--slice", str(plate), "--datadir", os.path.join(out, "cfg"), "--outputdir", out,
                          project], capture_output=True, text=True, timeout=3600)
    found = glob.glob(os.path.join(out, "*.gcode"))
    if len(found) != 1:
        raise RuntimeError(f"{len(found)} G-code files (exit {run.returncode}): {(run.stdout + run.stderr)[-600:]}")
    return found[0]


def _facts(gcode):
    with open(gcode, errors="replace") as f:
        text = f.read()
    g, mins, _ = SA.stats(gcode)
    start = re.search(r"^G9111 .*$", text, re.M)
    return g, mins, start.group(0) if start else None


def build():
    beds = plan()
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (label, mat, items, _) in enumerate(beds, start=1):
            dst = os.path.join(tmp, f"bed{i}.3mf")
            bed_3mf(items, label, dst)
            parts.append((label, dst))
        need = sum(c for lab, _, its, opt in beds if not opt for _, c in its)
        title = f"Inverted pendulum - Kobra S1, the parts still to print ({need} parts, {len(beds)} beds)"
        desc = ("Filament 1 = PLA, 2 = PETG; one material per bed, in print order: " +
                "; ".join(lab for lab, *_ in beds))
        MP.write(MP.assemble(parts, title, desc, stamp(beds)), PATH)
    return beds


def stale():
    if not os.path.exists(PATH):
        return [f"3mf/{os.path.basename(PATH)} missing"]
    import zipfile
    with zipfile.ZipFile(PATH) as z:
        model = z.read("3D/3dmodel.model").decode(errors="replace")
    return [] if stamp() in model else [f"3mf/{os.path.basename(PATH)} is stale: run make_to_print.py"]


def verify(beds):
    """Each bed of the project against the same bed sliced alone with its material's presets."""
    bad, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "project.3mf")
        MP._unnamed(PATH, src)
        for p, (label, mat, items, _) in enumerate(beds, start=1):
            try:
                g1, m1, t1 = _facts(_slice(src, p, os.path.join(tmp, f"p{p}")))
                own = os.path.join(tmp, f"own{p}")
                os.makedirs(own)
                stls, _, settings = _bed_files(items, label, own)
                ref = os.path.join(tmp, f"own{p}.3mf")
                _export(stls, SA.PROCESS[("s1", mat)], [SA.FILAMENT[mat]], None, settings, ref, own)
                g2, m2, t2 = _facts(_slice(ref, 0, os.path.join(tmp, f"own{p}_sliced")))
            except RuntimeError as exc:
                bad.append(f"bed {p} ({label}): {exc}")
                continue
            if g1 is None or g2 is None or abs(g1 - g2) > 0.01 * g2 + 0.1 or t1 != t2:
                bad.append(f"bed {p} ({label}): {g1} g, '{t1}' in the project; {g2} g, '{t2}' on its own")
            else:
                rows.append((p, mat, g1, m1, t1))
    return rows, bad


def main(check=False):
    beds = build()
    print(f"wrote {os.path.relpath(PATH, G.ROOT)}: {len(beds)} beds, {os.path.getsize(PATH) // 1024} KB")
    for label, *_ in beds:
        print("  ", label)
    if not check:
        return True
    rows, bad = verify(beds)
    for p, mat, g, mins, t in rows:
        print(f"   bed {p} {mat.upper():4s} {g:6.1f} g {mins / 60:5.2f} h  {t}")
    print(f"sliced on its own, {len(rows)}/{len(beds)} beds print what the same bed prints with its own "
          f"material's presets")
    for b in bad:
        print("FAILED", b)
    return not bad


if __name__ == "__main__":
    sys.exit(0 if main("--verify" in sys.argv[1:]) else 1)

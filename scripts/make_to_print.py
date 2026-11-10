"""One slicer project with only the parts still to print: 3mf/to_print_kobra_s1.3mf.

The complete project (make_projects.py) prints every part. The owner reuses parts he already has,
so this one leaves out what he keeps (HAVE), takes one angle sensor's parts (SENSOR), and packs the
rest onto as few beds as fit, one material per bed: the PETG beds first, then the PLA ones, each in
print order, built like the complete project (make_projects.bed_3mf): two filaments, 1 = PLA (blue)
and 2 = PETG (orange), no prime tower, the PLA process with each PETG object carrying what the PETG
process changes (its infill). Parts that may not be needed (MAYBE) go on beds of their own, named
so: print those only if you need them. The gate checks the written project (audit()).

Edit HAVE, MAYBE and SENSOR below, then run: python scripts/make_to_print.py [--verify]
--verify slices every bed of the project (plate names blanked: the CLI crashes on them) and the
same bed again on its own with its material's own presets: both must give the same grams and the
same bed and nozzle temperatures.
"""
import os
import sys
import tempfile
import zipfile

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
MATERIALS = ("petg", "pla")             # bed order: PETG first (the belt drive is test-fitted first), then PLA


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
    """[(label, material, items, maybe)]: one material per bed, all PETG beds, then all PLA ones;
    within a material the needed beds in print order, then the optional ones."""
    need, maybe = wanted()
    beds = [(mat, items, False) for mat, items in pack(need)] + [(mat, items, True) for mat, items in pack(maybe)]
    beds.sort(key=lambda b: MATERIALS.index(b[0]))
    total = {m: sum(b[0] == m for b in beds) for m in MATERIALS}
    seen = dict.fromkeys(MATERIALS, 0)
    out = []
    for mat, items, opt in beds:
        seen[mat] += 1
        n = sum(c for _, c in items)
        names = [nm if c == 1 else f"{c} x {nm}" for nm, c in items]
        text = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")
        label = f"{len(out) + 1} {mat.upper()} {seen[mat]}/{total[mat]} - {text} ({n} part{'s' * (n > 1)})"
        out.append((label + (f" - OPTION, {MAYBE_WHY}" if opt else ""), mat, items, opt))
    return out


def stamp(beds=None):
    """Hash of the presets, the colours, the beds and their layouts (make_projects.stamp)."""
    return MP.stamp(beds or plan())


def build():
    beds = plan()
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (label, mat, items, _) in enumerate(beds, start=1):
            dst = os.path.join(tmp, f"bed{i}.3mf")
            MP.bed_3mf(items, label, dst)
            parts.append((label, dst))
        need = sum(c for lab, _, its, opt in beds if not opt for _, c in its)
        title = f"Inverted pendulum - Kobra S1, the parts still to print ({need} parts, {len(beds)} beds)"
        desc = ("Filament 1 = PLA, 2 = PETG; one material per bed, in print order: " +
                "; ".join(lab for lab, *_ in beds))
        MP.write(MP.assemble(parts, title, desc, stamp(beds)), PATH)
    return beds


def stale():
    """Problems the gate reports: the project missing, not built from the current parts and choices,
    or failing audit()."""
    if not os.path.exists(PATH):
        return [f"3mf/{os.path.basename(PATH)} missing"]
    with zipfile.ZipFile(PATH) as z:
        model = z.read("3D/3dmodel.model").decode(errors="replace")
    if stamp() not in model:
        return [f"3mf/{os.path.basename(PATH)} is stale: run make_to_print.py"]
    return audit()


def audit():
    """The written project, bed by bed (make_projects.audit): one material, every object on that
    material's filament with its own settings, each copy to print exactly once."""
    need, maybe = wanted()
    want = {}
    for name, c in need + maybe:
        want[name] = want.get(name, 0) + c
    return MP.audit(PATH, plan(), want)


def verify(beds):
    """Each bed of the project against the same bed sliced alone with its material's presets."""
    bad, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "project.3mf")
        MP._unnamed(PATH, src)
        for p, (label, mat, items, _) in enumerate(beds, start=1):
            try:
                g1, m1, t1 = MP.facts(MP.slice_plate(src, p, os.path.join(tmp, f"p{p}")))
                own = os.path.join(tmp, f"own{p}")
                os.makedirs(own)
                stls, _, settings = MP.bed_files(items, label, own)
                ref = os.path.join(tmp, f"own{p}.3mf")
                MP.export(stls, SA.PROCESS[("s1", mat)], [SA.FILAMENT[mat]], None, settings, ref, own)
                g2, m2, t2 = MP.facts(MP.slice_plate(ref, 0, os.path.join(tmp, f"own{p}_sliced")))
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

"""The complete slicer project: every plate, PETG and PLA, as a named plate in print order in one
project for the Kobra S1 (open it, pick a plate, slice it, send it): 3mf/complete_project_kobra_s1.3mf.

Two filaments, 1 = PLA (blue) and 2 = PETG (orange), and no prime tower: each plate holds one
material, every object on that material's filament, so it prints with that filament's temperatures
and cooling. The process is the PLA one; every PETG object carries what the PETG process changes
(its infill). Each plate's layout is the plate's own (plates.py), so it prints what that plate's own
G-code (gcode/s1_<material>_plates/) prints. make_to_print.py builds the project of the parts still
to print the same way. The slicer's CLI cannot assemble such a project and crashes on any plate
name, so `--verify` slices a copy with the names blanked, plate by plate, and checks each against its
plate's G-code: the same grams, the same bed and nozzle temperatures.

Run: python scripts/make_projects.py [--verify]
"""
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

import geom as G
import plates as PT
import slice_all as SA
from make_print_ready import PARTS

PATH = os.path.join(G.ROOT, "3mf", "complete_project_kobra_s1.3mf")
META = "pendulum_jobs_sha256"
GAP = 0.2            # the slicer lays plates out 1.2 bed widths apart
DATE = (2026, 1, 1, 0, 0, 0)
FIL = {"pla": 1, "petg": 2}             # the projects' filament slots
COLOUR = {"pla": "#3A86FF", "petg": "#F2754E"}   # so the slicer shows PLA and PETG plates apart


def _profile(name):
    with open(os.path.join(SA.PROFILES, name)) as f:
        return json.load(f)


def petg_overrides():
    """What the PETG process changes against the PLA one: set on each PETG object."""
    pla, petg = _profile(SA.PROCESS[("s1", "pla")]), _profile(SA.PROCESS[("s1", "petg")])
    return {k: v for k, v in petg.items() if k != "name" and pla.get(k) != v}


def plan():
    """[(label, material, items, optional)]: every plate of plates.py in print order."""
    total = {m: sum(PT.material(p) == m for p in PT.PLATES) for m in FIL}
    seen, out = dict.fromkeys(FIL, 0), []
    for i, (plate, items) in enumerate(PT.PLATES.items(), start=1):
        mat = PT.material(plate)
        seen[mat] += 1
        n = sum(c for _, c in items)
        theme = re.sub(r"^(pla|petg)_\d+_", "", plate).replace("_", " ")
        opt = any(PARTS[name]["optional"] for name, _ in items)
        label = f"{i} {mat.upper()} {seen[mat]}/{total[mat]} - {theme} ({n} part{'s' * (n > 1)})"
        out.append((label + (" - OPTION" if opt else ""), mat, tuple(items), opt))
    return out


def stamp(beds):
    """Hash of the presets (parsed, so line endings do not count), the colours, and each bed: its
    label, material, and each copy's STL, place and own settings."""
    h = hashlib.sha256()
    for f in (SA.MACHINE["s1"], SA.PROCESS[("s1", "pla")], SA.PROCESS[("s1", "petg")], SA.FILAMENT["pla"],
              SA.FILAMENT["petg"]):
        h.update(json.dumps(_profile(f), sort_keys=True).encode())
    h.update(json.dumps(COLOUR, sort_keys=True).encode())
    for label, mat, items, _ in beds:
        h.update(json.dumps([label, mat]).encode())
        for name, k, x, y, a in PT.layout_items(tuple(items), label):
            h.update(SA.stl_hash(name).encode())
            h.update(json.dumps([name, k, x, y, a, SA.object_settings(name)], sort_keys=True).encode())
    return h.hexdigest()


def bed_files(items, label, tmp):
    """Each copy's STL where it prints on the bed, its material, and its own slicer settings."""
    copies = dict(items)
    stls, mats, own = [], [], {}
    for name, k, x, y, a in PT.layout_items(tuple(items), label):
        obj = PT.stl_name(name, k, copies[name]) + ".stl"
        path = os.path.join(tmp, obj)
        G.write_stl(path, PT.placed_mesh(name, x, y, a))
        stls.append(path)
        mats.append(PARTS[name]["material"])
        if SA.object_settings(name):
            own[obj] = SA.object_settings(name)
    return stls, mats, own


def export(stls, process, filaments, ids, own, dst, tmp):
    """The STLs, where they lie, as a project 3MF with these presets (ids: each object's filament),
    the objects in `own` with their own settings."""
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
    """One bed as a two-filament project: PLA objects on filament 1, PETG on 2 with the PETG process's
    changes; each filament its own colour, no prime tower (no bed mixes the two)."""
    over = petg_overrides()
    with tempfile.TemporaryDirectory() as tmp:
        stls, mats, own = bed_files(items, label, tmp)
        for path, mat in zip(stls, mats):
            if mat == "petg":
                obj = os.path.basename(path)
                own[obj] = {**over, **own.get(obj, {})}
        export(stls, SA.PROCESS[("s1", "pla")], [SA.FILAMENT["pla"], SA.FILAMENT["petg"]],
               [str(FIL[m]) for m in mats], own, dst, tmp)
    with zipfile.ZipFile(dst) as z:
        files = [(info, z.read(info.filename)) for info in z.infolist()]
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in files:
            if info.filename == "Metadata/project_settings.config":
                ps = json.loads(data)
                ps["filament_colour"] = [COLOUR[m] for m in sorted(FIL, key=FIL.get)]
                ps["enable_prime_tower"] = "0"
                data = json.dumps(ps, indent=4).encode()
            z.writestr(info, data)


def slice_plate(project, plate, out):
    """Slice plate `plate` (from 1; 0 = all) of a project into the new folder `out`: the G-code's path."""
    os.makedirs(out)
    run = subprocess.run([SA.SLICER, "--slice", str(plate), "--datadir", os.path.join(out, "cfg"), "--outputdir", out,
                          project], capture_output=True, text=True, timeout=3600)
    found = glob.glob(os.path.join(out, "*.gcode"))
    if len(found) != 1:
        raise RuntimeError(f"{len(found)} G-code files (exit {run.returncode}): {(run.stdout + run.stderr)[-600:]}")
    return found[0]


def facts(gcode):
    """(grams, minutes, the start line that sets the bed and nozzle temperatures) of a G-code file."""
    with open(gcode, errors="replace") as f:
        text = f.read()
    g, mins, _ = SA.stats(gcode)
    start = re.search(r"^G9111 .*$", text, re.M)
    return g, mins, start.group(0) if start else None


def plate_grid(count):
    with open(os.path.join(SA.PROFILES, SA.MACHINE["s1"])) as f:
        area = [[float(c) for c in p.split("x")] for p in json.load(f)["printable_area"]]
    w = max(p[0] for p in area) - min(p[0] for p in area)
    d = max(p[1] for p in area) - min(p[1] for p in area)
    root = math.sqrt(count)
    cols = int(round(root)) + (1 if root > round(root) else 0)
    return [((i % cols) * w * (1 + GAP), -(i // cols) * d * (1 + GAP)) for i in range(count)]


def _read(path):
    with zipfile.ZipFile(path) as z:
        model = z.read("3D/3dmodel.model").decode()
        ms = z.read("Metadata/model_settings.config").decode()
        items = dict(re.findall(r'<item objectid="(\d+)"[^>]*?transform="([^"]+)"', model))
        blocks = {m.group(1): m.group(0) for m in re.finditer(r'<object id="(\d+)">.*?</object>', ms, re.S)}
        objs = []
        for oid, comp in re.findall(r'<object id="(\d+)"[^>]*type="model">\s*<components>(.*?)</components>', model, re.S):
            path3, sub_id, transform = re.search(r'p:path="([^"]+)" objectid="(\d+)"[^>]*?transform="([^"]+)"', comp).groups()
            name = re.search(r'<metadata key="name" value="([^"]+)"', blocks[oid]).group(1)
            objs.append(dict(name=name, mesh=z.read(path3.lstrip("/")).decode(), sub_id=sub_id, component=transform,
                             item=items[oid], block=blocks[oid]))
        shared = {n: z.read(n) for n in ("[Content_Types].xml", "_rels/.rels", "Metadata/slice_info.config")}
        header = model[:model.index("<resources>")]
        settings = z.read("Metadata/project_settings.config")
    return objs, shared, header, settings


def _shift(transform, dx, dy):
    v = transform.split()
    v[9], v[10] = repr(float(v[9]) + dx), repr(float(v[10]) + dy)
    return " ".join(v)


def assemble(plan, title, desc, stamp):
    """One project from plate projects [(plate label, its 3MF)]: their objects, placements and
    settings copied unchanged, one named plate each, in order. Every 3MF must carry the same
    project settings (printer, process, filaments)."""
    origins = plate_grid(len(plan))
    out, rels, resources, items, blocks, plates = {}, [], [], [], [], []
    shared = header = settings = None
    k = 0
    for p, ((label, path), (ox, oy)) in enumerate(zip(plan, origins), start=1):
        objs, sh, hd, st = _read(path)
        if settings is None:
            shared, header, settings = sh, hd, st
        elif st != settings:
            raise RuntimeError(f"{label}: its 3MF's settings differ from the project's first plate")
        instances = []
        for o in objs:
            k += 1
            top, sub = 2 * k, 2 * k - 1
            path3 = f"/3D/Objects/{o['name']}_{k}.model"
            mesh = re.sub(r'<object id="\d+" p:UUID="[^"]+"',
                          f'<object id="{sub}" p:UUID="{k:04x}0000-81cb-4c03-9d28-80fed5dfa1dc"', o["mesh"], count=1)
            out[path3.lstrip("/")] = mesh.encode()
            rels.append(f' <Relationship Target="{path3}" Id="rel-{k}" '
                        f'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>')
            resources.append(f'  <object id="{top}" p:UUID="{k:08x}-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n'
                             f'   <components>\n    <component p:path="{path3}" objectid="{sub}" '
                             f'p:UUID="{k:04x}0000-b206-40ff-9872-83e8017abed1" transform="{o["component"]}"/>\n'
                             f'   </components>\n  </object>')
            items.append(f'  <item objectid="{top}" p:UUID="{top:08x}-b1ec-4553-aec9-835e5b724bb4" '
                         f'transform="{_shift(o["item"], ox, oy)}" printable="1"/>')
            block = re.sub(r'<object id="\d+">', f'<object id="{top}">', o["block"], count=1)
            blocks.append("  " + re.sub(r'<part id="\d+"', f'<part id="{sub}"', block, count=1))
            instances.append(f'    <model_instance>\n      <metadata key="object_id" value="{top}"/>\n'
                             f'      <metadata key="instance_id" value="0"/>\n'
                             f'      <metadata key="identify_id" value="{1000 + k}"/>\n    </model_instance>')
        plates.append(f'  <plate>\n    <metadata key="plater_id" value="{p}"/>\n'
                      f'    <metadata key="plater_name" value="{escape(label, {chr(34): "&quot;"})}"/>\n'
                      f'    <metadata key="locked" value="false"/>\n' + "\n".join(instances) + "\n  </plate>")
    header = re.sub(r'\s*<metadata name="pendulum_stl_sha256">[^<]*</metadata>', "", header).replace("<resources>", "")
    header = re.sub(r'<metadata name="Title">[^<]*</metadata>', f'<metadata name="Title">{escape(title)}</metadata>', header)
    header = re.sub(r'<metadata name="Description">[^<]*</metadata>',
                    f'<metadata name="Description">{escape(desc)}</metadata>', header)
    header = header.rstrip() + f'\n <metadata name="{META}">{stamp}</metadata>\n'
    out["3D/3dmodel.model"] = (header + " <resources>\n" + "\n".join(resources) + "\n </resources>\n"
                               ' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n' + "\n".join(items) +
                               "\n </build>\n</model>\n").encode()
    out["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships '
                                          'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                                          + "\n".join(rels) + "\n</Relationships>\n").encode()
    out["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "\n".join(blocks)
                                             + "\n" + "\n".join(plates) + "\n  <assemble>\n  </assemble>\n</config>\n").encode()
    out["Metadata/project_settings.config"] = settings
    out.update(shared)
    order = (["[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model", "3D/_rels/3dmodel.model.rels"] +
             sorted(n for n in out if n.startswith("3D/Objects/")) +
             ["Metadata/project_settings.config", "Metadata/model_settings.config", "Metadata/slice_info.config"])
    return {n: out[n] for n in order}


def write(files, dst):
    tmp = dst + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    os.replace(tmp, dst)
    return dst


def build():
    beds = plan()
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (label, _, items, _) in enumerate(beds, start=1):
            dst = os.path.join(tmp, f"plate{i}.3mf")
            bed_3mf(items, label, dst)
            parts.append((label, dst))
        n = sum(c for _, _, items, _ in beds for _, c in items)
        title = f"Inverted pendulum - Kobra S1, every part ({n} parts, {len(beds)} plates)"
        desc = ("Filament 1 = PLA, 2 = PETG; one material per plate, in print order (tracker.md): " +
                "; ".join(lab for lab, *_ in beds))
        write(assemble(parts, title, desc, stamp(beds)), PATH)
    return beds


def audit(path, beds, want):
    """A written two-filament project, plate by plate: one material, every object on that material's
    filament with its own settings from the print table (and, PETG ones, the PETG process's changes),
    each copy exactly once (want: {part: copies}); the filaments coloured apart, no prime tower."""
    rel = f"3mf/{os.path.basename(path)}"
    with zipfile.ZipFile(path) as z:
        ms = z.read("Metadata/model_settings.config").decode(errors="replace")
        ps = json.loads(z.read("Metadata/project_settings.config"))
    order = sorted(FIL, key=FIL.get)
    bad = []
    if ps.get("filament_type") != [m.upper() for m in order]:
        bad.append(f"{rel}: filaments {ps.get('filament_type')}, not {[m.upper() for m in order]}")
    if ps.get("filament_colour") != [COLOUR[m] for m in order] or len(set(COLOUR.values())) != len(FIL):
        bad.append(f"{rel}: filament colours {ps.get('filament_colour')}")
    if str(ps.get("enable_prime_tower")) != "0":
        bad.append(f"{rel}: prime tower on")
    objs = {m.group(1): m.group(0) for m in re.finditer(r'<object id="(\d+)">.*?</object>', ms, re.S)}
    plates = re.findall(r"<plate>(.*?)</plate>", ms, re.S)
    if len(plates) != len(beds):
        bad.append(f"{rel}: {len(plates)} plates, the plan has {len(beds)}")
    over = petg_overrides()
    count = {}
    for p, ((label, mat, _, _), plate) in enumerate(zip(beds, plates), start=1):
        name = re.search(r'plater_name" value="([^"]*)"', plate).group(1)
        if name != escape(label, {'"': "&quot;"}):
            bad.append(f"{rel} plate {p}: named '{name}'")
        for oid in re.findall(r'object_id" value="(\d+)"', plate):
            block = objs[oid]
            stl = re.search(r'key="name" value="([^"]+)\.stl"', block).group(1)
            part = stl if stl in PARTS else re.sub(r"_\d+$", "", stl)
            count[part] = count.get(part, 0) + 1
            fil = re.search(r'key="extruder" value="(\d+)"', block).group(1)
            if PARTS.get(part, {}).get("material") != mat or fil != str(FIL[mat]):
                bad.append(f"{rel} plate {p} ({mat.upper()}): {stl} is {PARTS.get(part, {}).get('material')} "
                           f"on filament {fil}")
            need = {**(over if mat == "petg" else {}), **(SA.object_settings(part) if part in PARTS else {})}
            if any(f'key="{k}" value="{v}"' not in block for k, v in need.items()):
                bad.append(f"{rel} plate {p}: {stl} lacks its own settings {need}")
    if count != want:
        bad.append(f"{rel}: copies {count} against {want}")
    return bad


def stale():
    """Problems the gate reports: the project missing, not built from the current plates, parts and
    presets, or failing audit()."""
    if not os.path.exists(PATH):
        return [f"3mf/{os.path.basename(PATH)} missing"]
    with zipfile.ZipFile(PATH) as z:
        model = z.read("3D/3dmodel.model").decode(errors="replace")
    beds = plan()
    if stamp(beds) not in model:
        return [f"3mf/{os.path.basename(PATH)} is stale: run make_projects.py"]
    return audit(PATH, beds, {name: spec["qty"] for name, spec in PARTS.items()})


def _unnamed(src, dst):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = zi.read(info.filename)
            if info.filename == "Metadata/model_settings.config":
                data = re.sub(rb'(<metadata key="plater_name" value=")[^"]*"', rb'\1"', data)
            zo.writestr(info, data)


def verify(beds):
    """Each plate of the project, sliced on its own (names blanked), against its plate's own G-code:
    the same grams, the same bed and nozzle temperatures."""
    bad, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "project.3mf")
        _unnamed(PATH, src)
        for p, ((label, mat, _, _), plate) in enumerate(zip(beds, PT.PLATES), start=1):
            try:
                g1, m1, t1 = facts(slice_plate(src, p, os.path.join(tmp, f"p{p}")))
            except RuntimeError as exc:
                bad.append(f"plate {p} ({label}): {exc}")
                continue
            g2, _, t2 = facts(PT.gcode_path(plate))
            if g1 is None or g2 is None or abs(g1 - g2) > 0.01 * g2 + 0.1 or t1 != t2:
                bad.append(f"plate {p} ({label}): {g1} g, '{t1}' in the project; {g2} g, '{t2}' in "
                           f"{os.path.relpath(PT.gcode_path(plate), G.ROOT)}")
            else:
                rows.append((p, mat, g1, m1, t1))
    return rows, bad


def main(check=False):
    beds = build()
    print(f"wrote {os.path.relpath(PATH, G.ROOT)}: {len(beds)} plates, {os.path.getsize(PATH) // 1024} KB")
    for label, *_ in beds:
        print("  ", label)
    if not check:
        return True
    rows, bad = verify(beds)
    for p, mat, g, mins, t in rows:
        print(f"   plate {p} {mat.upper():4s} {g:6.1f} g {mins / 60:5.2f} h  {t}")
    print(f"sliced on its own, {len(rows)}/{len(beds)} plates print what their own G-code prints")
    for b in bad:
        print("FAILED", b)
    return not bad


if __name__ == "__main__":
    sys.exit(0 if main("--verify" in sys.argv[1:]) else 1)

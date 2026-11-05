"""Complete slicer projects, one per material, every plate of that material as a named plate in
print order (open one, pick a plate, slice it, send it):
- 3mf/complete_project_kobra_s1_pla.3mf
- 3mf/complete_project_kobra_s1_petg.3mf
A slicer project holds one filament setting, so there is one per material. Each is assembled
from the plates' own 3MF projects (slice_all.py), whose G-code the gate checks: their objects,
placements and settings are copied unchanged. The slicer's CLI cannot assemble such a project and
crashes on any plate name, so `--verify` slices a copy with the names blanked, plate by plate,
and checks each prints what its plate's G-code prints (the VTOL project's method).

Run: python scripts/make_projects.py [--verify]
"""
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

import geom as G
import plates as PT
import slice_all as SA
from make_print_ready import PARTS

PROJECTS = {"pla": "complete_project_kobra_s1_pla.3mf", "petg": "complete_project_kobra_s1_petg.3mf"}
META = "pendulum_jobs_sha256"
GAP = 0.2            # the slicer lays plates out 1.2 bed widths apart
DATE = (2026, 1, 1, 0, 0, 0)


def project_path(material):
    return os.path.join(G.ROOT, "3mf", PROJECTS[material])


def jobs(material):
    """[(plate label, plate, G-code path, stamp, object names)] in print order."""
    out = []
    for plate, items in PT.PLATES.items():
        if PT.material(plate) != material:
            continue
        copies = dict(items)
        objs = [PT.stl_name(n, k, copies[n]) + ".stl" for n, k, _, _, _ in PT.layout(plate)]
        theme = re.sub(r"^(pla|petg)_\d+_", "", plate).replace("_", " ")
        opt = any(PARTS[n]["optional"] for n, _ in items)
        label = f"{material.upper()} {len(out) + 1} - {theme} ({len(objs)} parts)" + (" - OPTION" if opt else "")
        out.append((label, plate, PT.gcode_path(plate), PT.plate_hash(plate), objs))
    return out


def project_stamp(material):
    return hashlib.sha256("\n".join(f"{lab}:{st}" for lab, _, _, st, _ in jobs(material)).encode()).hexdigest()


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


def entries(material):
    plan = jobs(material)
    origins = plate_grid(len(plan))
    out, rels, resources, items, blocks, plates = {}, [], [], [], [], []
    shared = header = settings = None
    k = 0
    for p, ((label, job, gcode, _, _), (ox, oy)) in enumerate(zip(plan, origins), start=1):
        objs, sh, hd, st = _read(SA.path_3mf(gcode))
        if settings is None:
            shared, header, settings = sh, hd, st
        elif st != settings:
            raise RuntimeError(f"{job}: its 3MF's settings differ from the project's first plate")
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
    title = f"Inverted pendulum - Kobra S1, {material.upper()} ({len(plan)} plates)"
    desc = "One plate per print job, in print order (tracker.md): " + "; ".join(lab for lab, *_ in plan)
    header = re.sub(r'<metadata name="Title">[^<]*</metadata>', f'<metadata name="Title">{escape(title)}</metadata>', header)
    header = re.sub(r'<metadata name="Description">[^<]*</metadata>',
                    f'<metadata name="Description">{escape(desc)}</metadata>', header)
    header = header.rstrip() + f'\n <metadata name="{META}">{project_stamp(material)}</metadata>\n'
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


def build(material):
    files = entries(material)
    dst = project_path(material)
    tmp = dst + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    os.replace(tmp, dst)
    return dst


def stale():
    """Problems the gate reports: a project missing or not built from the current plates."""
    bad = []
    for material in PROJECTS:
        path = project_path(material)
        if not os.path.exists(path):
            bad.append(f"3mf/{PROJECTS[material]} missing")
            continue
        with zipfile.ZipFile(path) as z:
            model = z.read("3D/3dmodel.model").decode(errors="replace")
        if project_stamp(material) not in model:
            bad.append(f"3mf/{PROJECTS[material]} is stale: run make_projects.py")
    return bad


def _unnamed(src, dst):
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = zi.read(info.filename)
            if info.filename == "Metadata/model_settings.config":
                data = re.sub(rb'(<metadata key="plater_name" value=")[^"]*"', rb'\1"', data)
            zo.writestr(info, data)


def _mass(path):
    with open(path, errors="replace") as f:
        m = re.search(r"; total filament used \[g\] = ([\d.]+)", f.read())
    return float(m.group(1)) if m else None


def verify(material):
    """Slice each plate of the project on its own (names blanked) and compare its filament mass
    and layer count with the plate's G-code."""
    plan = jobs(material)
    bad, same = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, os.path.basename(project_path(material)))
        _unnamed(project_path(material), src)
        for p, (label, job, gcode, _, _) in enumerate(plan, start=1):
            out = os.path.join(tmp, f"p{p}")
            os.makedirs(out)
            run = subprocess.run([SA.SLICER, "--slice", str(p), "--datadir", os.path.join(out, "cfg"),
                                  "--outputdir", out, src], capture_output=True, text=True, timeout=3600)
            found = glob.glob(os.path.join(out, "*.gcode"))
            if len(found) != 1:
                bad.append(f"plate {p} ({label}): {len(found)} G-code files (exit {run.returncode})")
                continue
            a, b = _mass(found[0]), _mass(gcode)
            if a is None or b is None or abs(a - b) > 0.01 * b + 0.1:
                bad.append(f"plate {p} ({label}): {a} g against {b} g in its G-code")
            else:
                same += 1
    return same, len(plan), bad


def main(check=False):
    failed = []
    for material in PROJECTS:
        dst = build(material)
        line = f"wrote {os.path.relpath(dst, G.ROOT)}: {len(jobs(material))} plates, {os.path.getsize(dst) // 1024} KB"
        if check:
            same, n, bad = verify(material)
            line += f"; sliced on its own, {same}/{n} plates print what their G-code prints"
            failed += bad
        print(line)
    for b in failed:
        print("FAILED", b)
    return not failed


if __name__ == "__main__":
    sys.exit(0 if main("--verify" in sys.argv[1:]) else 1)

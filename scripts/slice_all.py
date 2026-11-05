"""Slice every print-ready part and every plate with Anycubic Slicer Next (OrcaSlicer's CLI works
the same; set PENDULUM_SLICER if it is not at the default Windows path).

Each job is first laid out as a project 3MF, which is then sliced on its own:
- 3mf/s1_<pla|petg>/<part>.3mf and 3mf/s1_<pla|petg>_plates/<plate>.3mf: open one in the slicer
  to send the job to the printer; it carries the parts where they print and every setting.
- gcode/<same folder>/<same name>.gcode: what slicing that 3MF gives.
Each G-code file ends with a `; pendulum_stl_sha256 = ...` stamp naming the STL (or, for a plate,
the STLs and places) it was sliced from, and its 3MF carries the same hash as metadata, so
check_parts.py can tell stale files from current ones (git keeps no file times).

Run: python scripts/slice_all.py [part or plate ...]
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
import zipfile

import geom as G
import plates as PT
from make_print_ready import PARTS

SLICER = os.environ.get("PENDULUM_SLICER", r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
PROFILES = os.path.join(G.ROOT, "slicer_profiles")
MACHINE = {"s1": "machine_kobra_s1.json"}
PROCESS = {("s1", "pla"): "process_pla.json", ("s1", "petg"): "process_petg.json"}
FILAMENT = {"pla": "filament_pla.json", "petg": "filament_petg.json"}
STAMP = "; pendulum_stl_sha256 = "
META_3MF = "pendulum_stl_sha256"


def stl_hash(name):
    with open(os.path.join(G.PRINT, name + ".stl"), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def out_path(name):
    spec = PARTS[name]
    return os.path.join(G.ROOT, "gcode", f"{spec['printer']}_{spec['material']}", name + ".gcode")


def path_3mf(gcode):
    folder = os.path.basename(os.path.dirname(gcode))
    return os.path.join(G.ROOT, "3mf", folder, os.path.splitext(os.path.basename(gcode))[0] + ".3mf")


def preset_names(material):
    names = []
    for fname in (MACHINE["s1"], PROCESS[("s1", material)], FILAMENT[material]):
        with open(os.path.join(PROFILES, fname)) as f:
            names.append(json.load(f)["name"])
    return tuple(names)


def _run(cmd, what):
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return run, f"{what} (exit {run.returncode})\n{(run.stdout + run.stderr)[-1500:]}"


def object_settings(name):
    spec = PARTS[name]
    out = {"brim_type": "outer_only", "brim_width": f"{spec['brim']:g}"} if spec["brim"] else {}
    out.update(spec["slicer"])
    return out


def _set_object_settings(project, settings):
    """Give each object named in `settings` ({STL name: {key: value}}) its own settings in the 3MF."""
    with zipfile.ZipFile(project) as z:
        files = [(info, z.read(info.filename)) for info in z.infolist()]
    with zipfile.ZipFile(project, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in files:
            if info.filename == "Metadata/model_settings.config":
                text = data.decode()
                for stl, kv in settings.items():
                    head = (r'(<object id="\d+">\s*<metadata key="name" value="' + re.escape(stl) +
                            r'"/>\s*<metadata key="extruder" value="\d+"/>)')
                    meta = "".join(f'\n    <metadata key="{k}" value="{v}"/>' for k, v in kv.items())
                    text, n = re.subn(head, lambda m: m.group(1) + meta, text, count=1)
                    if n != 1:
                        raise RuntimeError(f"{stl}: no such object in {os.path.basename(project)}")
                data = text.encode()
            z.writestr(info, data)


def _slice(stls, material, dst, stamp, per_object=None):
    """Lay `stls` out on one bed as a project 3MF (--arrange 0 keeps each where it is), give the
    objects in `per_object` their own settings, then slice that 3MF on its own with a fresh
    settings folder: the G-code is what opening the 3MF and slicing it gives."""
    settings = [os.path.join(PROFILES, MACHINE["s1"]), os.path.join(PROFILES, PROCESS[("s1", material)])]
    project = path_3mf(dst)
    with tempfile.TemporaryDirectory() as tmp:
        name3 = os.path.basename(project)
        _, log = _run([SLICER, "--arrange", "0", "--orient", "0", "--ensure-on-bed",
                       "--datadir", os.path.join(tmp, "cfg"), "--load-settings", ";".join(settings),
                       "--load-filaments", os.path.join(PROFILES, FILAMENT[material]),
                       "--metadata-name", META_3MF, "--metadata-value", stamp,
                       "--export-3mf", name3, "--outputdir", tmp, *stls], f"{name3}: no 3MF written")
        made = os.path.join(tmp, name3)
        if not os.path.exists(made):
            raise RuntimeError(log)
        if per_object:
            _set_object_settings(made, per_object)
        sliced = os.path.join(tmp, "sliced")
        os.makedirs(sliced)
        _, log = _run([SLICER, "--slice", "0", "--arrange", "0", "--orient", "0",
                       "--datadir", os.path.join(tmp, "cfg_3mf"), "--outputdir", sliced, made],
                      f"{os.path.basename(dst)}: slicing the 3MF")
        found = glob.glob(os.path.join(sliced, "*.gcode"))
        if len(found) != 1:
            raise RuntimeError(f"{len(found)} G-code files from {log}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(found[0], dst)
        os.makedirs(os.path.dirname(project), exist_ok=True)
        shutil.move(made, project)
    with open(dst, "a", newline="\n") as f:
        f.write(f"{STAMP}{stamp}\n")
    return dst


def bed_centre():
    with open(os.path.join(PROFILES, MACHINE["s1"])) as f:
        corners = [[float(c) for c in corner.split("x")] for corner in json.load(f)["printable_area"]]
    xs, ys = zip(*corners)
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def slice_part(name):
    cx, cy = bed_centre()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, name + ".stl")
        G.write_stl(path, G.transform(G.read_stl(os.path.join(G.PRINT, name + ".stl")), None, (cx, cy, 0.0)))
        own = {name + ".stl": object_settings(name)} if object_settings(name) else None
        return _slice([path], PARTS[name]["material"], out_path(name), stl_hash(name), per_object=own)


def slice_plate(plate):
    copies = dict(PT.PLATES[plate])
    with tempfile.TemporaryDirectory() as tmp:
        stls, own = [], {}
        for name, k, x, y, angle in PT.layout(plate):
            path = os.path.join(tmp, PT.stl_name(name, k, copies[name]) + ".stl")
            G.write_stl(path, PT.placed_mesh(name, x, y, angle))
            stls.append(path)
            if object_settings(name):
                own[os.path.basename(path)] = object_settings(name)
        return _slice(stls, PT.material(plate), PT.gcode_path(plate), PT.plate_hash(plate), per_object=own)


def stats(path):
    """(grams, minutes, stamp) read from a G-code file's tail, or (None, None, None)."""
    if not os.path.exists(path):
        return None, None, None
    with open(path, "r", errors="replace") as f:
        f.seek(max(0, os.path.getsize(path) - 400_000))
        tail = f.read()
    m = re.search(r"; total filament used \[g\] = ([\d.]+)", tail)
    t = re.search(r"; estimated printing time \(normal mode\) = ([^\n]+)", tail)
    s = re.search(re.escape(STAMP) + r"([0-9a-f]{64})", tail)
    minutes = None
    if t:
        unit = dict(d=1440, h=60, m=1, s=1 / 60)
        minutes = sum(float(v) * unit[k] for v, k in re.findall(r"(\d+)([dhms])", t.group(1)))
    return (float(m.group(1)) if m else None), minutes, (s.group(1) if s else None)


def part_grams(name):
    """Sliced mass of one copy of a part, if its G-code is current."""
    g, _, stamp = stats(out_path(name))
    return g if g and stamp == stl_hash(name) else None


def expected_files():
    paths = [out_path(n) for n in PARTS] + [PT.gcode_path(p) for p in PT.PLATES]
    gc = {os.path.normcase(os.path.abspath(p)) for p in paths}
    tm = {os.path.normcase(os.path.abspath(path_3mf(p))) for p in paths}
    return gc, tm


def main(names=None):
    if not os.path.exists(SLICER):
        sys.exit(f"slicer not found: {SLICER} (set PENDULUM_SLICER)")
    full = not names
    names = names or sorted(PARTS) + list(PT.PLATES)
    failed = []
    for name in names:
        try:
            dst = slice_plate(name) if name in PT.PLATES else slice_part(name)
            g, mins, _ = stats(dst)
            print(f"sliced {name:24s} {g:7.1f} g {mins / 60:5.2f} h -> {os.path.relpath(dst, G.ROOT)}", flush=True)
        except Exception as exc:  # report every failure, keep slicing the rest
            failed.append(name)
            print(f"FAILED {name}: {exc}", flush=True)
    if full:
        gc, tm = expected_files()
        for keep, pattern in ((gc, ("gcode", "*", "*.gcode")), (tm, ("3mf", "*", "*.3mf"))):
            for path in glob.glob(os.path.join(G.ROOT, *pattern)):
                if os.path.normcase(os.path.abspath(path)) not in keep:
                    os.remove(path)
                    print(f"removed stray {os.path.relpath(path, G.ROOT)}")
    if failed:
        print(f"{len(failed)} files failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])

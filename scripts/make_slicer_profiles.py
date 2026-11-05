"""Self-contained slicer settings for the pendulum's prints (no `inherits` chains: the slicer's CLI
needs every value in one file).

Base files, committed: machine_kobra_s1.json, process_standard.json and filament_petg.json come
from the VTOL project (Anycubic Slicer Next 2.0.0.3's Kobra S1 0.4 presets, proven with its CLI).
This script derives the rest:
- process_pla.json / process_petg.json: 4 walls, 5 top and bottom layers, gyroid infill (25 % PLA,
  35 % PETG), no brim (parts that need one get it from the print table).
- filament_pla.json: the installed slicer's "Generic PLA @Anycubic Kobra S1 0.4 nozzle", resolved,
  bed 60 C on every plate type.
- filament_petg.json: renamed, bed 75 C on every plate type (as in the VTOL project).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "slicer_profiles"))
PRESETS = os.environ.get("ANYCUBIC_PRESETS", r"C:\Program Files\AnycubicSlicerNext\resources\profiles\Anycubic")
PLATE_TYPES = ("cool", "eng", "hot", "textured", "textured_cool", "supertack")


def bed_temp(t):
    return {f"{plate}_plate_temp{layer}": [str(t)] for plate in PLATE_TYPES for layer in ("", "_initial_layer")}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolved(folder, name):
    data = load(os.path.join(PRESETS, folder, name + ".json"))
    base = {}
    inh = data.get("inherits")
    for parent in ([inh] if isinstance(inh, str) else inh or []):
        if parent:
            base.update(resolved(folder, parent))
    base.update({k: v for k, v in data.items() if k != "inherits"})
    return base


def write(name, data):
    with open(os.path.join(OUT, name), "w", newline="\n") as f:
        json.dump(data, f, indent=2)
    print(f"wrote slicer_profiles/{name} ({len(data)} keys)")


def main():
    std = load(os.path.join(OUT, "process_standard.json"))
    common = {"wall_loops": "4", "top_shell_layers": "5", "bottom_shell_layers": "5", "sparse_infill_pattern": "gyroid",
              "brim_type": "no_brim", "enable_support": "0", "detect_overhang_wall": "1"}
    for mat, infill in (("pla", "25%"), ("petg", "35%")):
        p = dict(std)
        p.update(common)
        p.update({"name": f"{mat.upper()} @pendulum", "sparse_infill_density": infill})
        write(f"process_{mat}.json", p)
    petg = load(os.path.join(OUT, "filament_petg.json"))
    petg.update({"name": "PETG @pendulum", **bed_temp(75)})
    write("filament_petg.json", petg)
    pla_path = os.path.join(OUT, "filament_pla.json")
    if os.path.isdir(PRESETS):
        pla = resolved("filament", "Generic PLA @Anycubic Kobra S1 0.4 nozzle")
        for k in ("setting_id", "instantiation", "base_id"):
            pla.pop(k, None)
    else:
        print(f"no presets at {PRESETS}: keeping the committed filament_pla.json")
        pla = load(pla_path)
    pla.update({"name": "PLA @pendulum", **bed_temp(60)})
    write("filament_pla.json", pla)


if __name__ == "__main__":
    main()

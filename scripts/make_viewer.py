"""Write viewer/manifest.json for the three.js viewer (viewer/index.html): every part and copy with
its placement and motion group, the hardware and bolts, the belt, the v0 machine with the audit's
findings, the simulated swing-up, the burst offsets and every print plate with its sliced mass
and time.

Run after assembly.py, sim.py and slicing; then `python scripts/serve_viewer.py`.
"""
import json
import os

import numpy as np

import geom as G
import plates as PT
import slice_all as SA
from make_print_ready import PARTS

PATH = os.path.join(G.ROOT, "viewer", "manifest.json")
SHARED = ("post_", "top_bar_", "bottom_bar_", "long_", "rod_", "sk8_", "sc8uu_")
# Burst view (mm): every part moves out the way it goes together.
BURST = {"carriage_plate": (0, 0, 70), "pivot_bridge": (0, 0, 130), "kp08_front": (0, 0, 175), "kp08_rear": (0, 0, 175),
         "pivot_shaft": (0, -60, 215), "pendulum_hub": (0, -130, 215), "pendulum_arm": (0, -170, 245),
         "pendulum_tip": (0, -170, 300), "magnet_cap": (0, 40, 215), "magnet": (0, 55, 215),
         "as5600_mount": (0, 70, 175), "as5600": (0, 85, 175), "lpd3806": (0, 95, 175), "coupler": (0, 45, 215),
         "belt_clamp": (0, 0, -60), "clamp_jaw": (0, 0, -95), "belt": (0, 0, -150),
         "motor_mount": (-70, 0, -50), "nema17": (-70, 90, -50), "motor_pulley": (-70, -70, -50),
         "pulley_flange_1": (-70, -100, -50), "idler_mount": (70, 0, -50), "idler_slider_1": (70, -60, -50),
         "idler_slider_2": (70, 60, -50), "idler_sleeve": (70, 0, -95), "idler_pulley": (70, -70, -75),
         "pulley_flange_2": (70, -100, -75), "electronics_tray": (0, 90, 0), "driver_board": (0, 90, 40),
         "controller": (0, 90, 40)}


def burst(name, M):
    if name in BURST:
        return list(BURST[name])
    t = np.asarray(M[12:15], float) if M is not None else np.zeros(3)
    if name.startswith("rod_bumper"):
        return [float(np.sign(t[0]) or 1) * 40, 0, 0]
    if name.startswith(("switch_mount", "endstop")):
        return [float(np.sign(t[0]) or 1) * 50, 0, 50]
    if name.startswith("cable_clip"):
        return [0, 35, 25]
    return [0, 0, 0]


def _stats(gcode, stamp):
    g, m, st = SA.stats(gcode)
    return (round(g, 1), round(m, 1)) if g is not None and st == stamp else (None, None)


def render():
    with open(G.ASSEMBLY_JSON) as f:
        A = json.load(f)
    with open(os.path.join(G.PARTS_DIR, "sim.json")) as f:
        sim = json.load(f)
    items = []
    for it in A["items"]:
        d = dict(it, url="../parts/" + it["file"], burst=None)
        d.pop("file")
        if it["kind"] == "vitamin":
            d["shared"] = it["name"].startswith(SHARED)
            # vitamins are exported in the assembly frame: their translation is in the mesh
            d["burst"] = burst(it["name"], None)
            mesh = G.read_stl(os.path.join(G.PARTS_DIR, it["file"]))
            lo, hi = G.bounds(mesh)
            d["centre"] = [round(float(v), 1) for v in (lo + hi) / 2]
        else:
            d["shared"] = False
            d["burst"] = burst(it["name"], it["matrix"])
            if it["kind"] == "printed":
                g, m = _stats(SA.out_path(it["part"]), SA.stl_hash(it["part"]))
                d.update(grams=g, minutes=m)
        items.append(d)
    plates = []
    for plate, lst in PT.PLATES.items():
        g, m = _stats(PT.gcode_path(plate), PT.plate_hash(plate))
        lay = [dict(part=n, k=k, x=x, y=y, angle=a, url=f"../parts/print_ready/{n}.stl") for n, k, x, y, a in PT.layout(plate)]
        plates.append(dict(name=plate, material=PT.material(plate), grams=g, minutes=m, items=lay,
                           option=any(PARTS[n]["optional"] for n, _ in lst)))
    v0 = [dict(v, url="../parts/" + v["file"]) for v in A["v0"]]
    for v in v0:
        v.pop("file")
    out = dict(version="v1", title="Inverted pendulum on a belt-driven cart", items=items, bolts=A["bolts"],
               hardware=A["hardware"], v0=v0, findings=A["findings"], layout=A["layout"], plates=plates, bed=PT.BED,
               sim=dict(trajectory=sim["trajectory"], swing_up_s=sim["swing_up_s"], x_max_m=sim["x_max_m"],
                        lqr_K=sim["lqr_K"], masses={k: v for k, v in sim["masses"].items() if not isinstance(v, dict)}))
    return json.dumps(out, indent=1) + "\n"


def current():
    if not os.path.exists(PATH):
        return None
    with open(PATH, encoding="utf-8") as f:
        return f.read()


def main():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    text = render()
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    m = json.loads(text)
    print(f"wrote viewer/manifest.json: {len(m['items'])} items, {len(m['bolts'])} bolts, {len(m['v0'])} v0 parts, "
          f"{len(m['plates'])} plates")


if __name__ == "__main__":
    main()

"""The print table and print orientation: every printed part, its material, copies, the rotation
that lays it on the Kobra S1's bed (proper rotations only), brim and per-part slicer settings.
Writes parts/print_ready/<part>.stl, centred on the bed, standing on z = 0.

Materials (one spool each): PETG where heat, wear or a clamped thread matters (motor mount next to
the motor, pulleys, idler parts, belt jaw, bumpers, hub, magnet cap, clips); PLA, stiffer, for the
carriage, bridge, clamp column, arm and brackets.
"""
import os

import numpy as np

import geom as G
import structure as S

BRIM = 5   # mm, outer brim for tall parts standing on a small base


def _p(name, brim=0, slicer=None, extra_rot=()):
    spec = S.PARTS[name]
    return dict(material=spec["material"], printer="s1", rot=list(spec["print"]) + list(extra_rot),
                qty=len(spec["copies"]), brim=brim, slicer=slicer or {}, role=spec["role"],
                optional=spec["group"].endswith("_opt"))


PARTS = {n: _p(n) for n in S.PARTS}
# Tall on a small footprint: a brim keeps the first layer down.
PARTS["idler_mount"] = _p("idler_mount", brim=BRIM)
PARTS["belt_clamp"] = _p("belt_clamp", brim=BRIM)
PARTS["switch_mount"] = _p("switch_mount", brim=BRIM)
# 287 mm long: diagonal on the 250 mm bed.
PARTS["pendulum_arm"] = _p("pendulum_arm", extra_rot=[("z", 45)])


def print_mesh(name):
    spec = PARTS[name]
    tris = G.read_stl(os.path.join(G.ASSEMBLY, name + ".stl"))
    R = np.eye(3)
    for axis, deg in spec["rot"]:
        R = G.rotation(axis, deg) @ R
    assert abs(np.linalg.det(R) - 1.0) < 1e-9, "print orientation must be a proper rotation"
    tris = G.transform(tris, R)
    lo, hi = G.bounds(tris)
    return G.transform(tris, None, (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))


def build():
    os.makedirs(G.PRINT, exist_ok=True)
    for f in os.listdir(G.PRINT):
        if f.endswith(".stl"):
            os.remove(os.path.join(G.PRINT, f))
    for name in sorted(PARTS):
        tris = print_mesh(name)
        G.write_stl(os.path.join(G.PRINT, name + ".stl"), tris)
        lo, hi = G.bounds(tris)
        ext = hi - lo
        print(f"{name:18s} {PARTS[name]['material']:5s} x{PARTS[name]['qty']}  {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f} mm"
              + ("  (option)" if PARTS[name]["optional"] else ""))


if __name__ == "__main__":
    build()

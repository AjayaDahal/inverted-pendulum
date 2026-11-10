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
# Taller than the side of a square of its first layer, a lever the nozzle can pry off the bed: a brim
# keeps the first layer down (the gate's bed check holds the rule). The sleeve stands 26 mm on 33 mm2.
for _name in ("idler_mount", "belt_clamp", "switch_mount", "idler_sleeve", "magnet_cap", "pendulum_tip"):
    PARTS[_name] = _p(_name, brim=BRIM)
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


def same_mesh(a, b, tol=1e-3):
    """The same surface to tol mm: when a part only moves, the CAD kernel reorders its triangles, splits
    flat faces along other diagonals and moves the last float digits. Same vertices, volume and area."""
    from scipy.spatial import cKDTree
    if a.shape != b.shape:
        return False
    pa, pb = a.reshape(-1, 3), b.reshape(-1, 3)
    if cKDTree(pb).query(pa)[0].max() > tol or cKDTree(pa).query(pb)[0].max() > tol:
        return False

    def area(t):
        return np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1).sum() / 2
    va, vb = abs(G.signed_volume(a)), abs(G.signed_volume(b))
    return abs(va - vb) <= 1e-6 * va + 1e-3 and abs(area(a) - area(b)) <= 1e-6 * area(a) + 1e-3


def build():
    os.makedirs(G.PRINT, exist_ok=True)
    for f in os.listdir(G.PRINT):
        if f.endswith(".stl") and f[:-4] not in PARTS:
            os.remove(os.path.join(G.PRINT, f))
    for name in sorted(PARTS):
        tris = print_mesh(name)
        path = os.path.join(G.PRINT, name + ".stl")
        if not (os.path.exists(path) and same_mesh(G.read_stl(path), tris)):   # unchanged: keep its bytes (G-code stamps)
            G.write_stl(path, tris)
        lo, hi = G.bounds(tris)
        ext = hi - lo
        print(f"{name:18s} {PARTS[name]['material']:5s} x{PARTS[name]['qty']}  {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:6.1f} mm"
              + ("  (option)" if PARTS[name]["optional"] else ""))


if __name__ == "__main__":
    build()

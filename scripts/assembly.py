"""The whole machine: every printed part's copies, the owner's hardware, the belt and the v0
(as photographed) parts, with their motion groups. Writes parts/assembly.json (read by the gate,
the viewer and sim.py), the hardware STLs, and parts/inverted_pendulum_v1.step.

Motion: the cart group moves by x along the rails; the pendulum group also turns by theta about
the pivot axis (y, through x and Z_SHAFT); the pulleys turn by x / (PD / 2) about their axles.
"""
import json
import math
import os
import sys

import numpy as np

import asbuilt as AB
import geom as G
import hardware as H
import params as P
import structure as S
import vitamins as V

GROUP_COLOURS = {"pla": "#e2873a", "petg": "#2f6db5"}
ROOT_REL = lambda p: os.path.relpath(p, G.ROOT).replace("\\", "/")   # noqa: E731


def pose(group, x=0.0, theta_deg=0.0):
    """4x4 motion of a group from the home pose."""
    T = G.mat4(None, (x, 0.0, 0.0))
    if group in ("cart", "cart_opt"):
        return T
    if group in ("pendulum", "pendulum_opt"):
        R = G.rotation("y", theta_deg)
        c = np.array([0.0, 0.0, P.Z_SHAFT])
        return T @ G.mat4(R, c - R @ c)
    if group in ("motor_pulley", "idler_pulley", "pulleys_m", "pulleys_i"):
        xc = P.X_MOTOR if group in ("motor_pulley", "pulleys_m") else P.X_IDLER
        R = G.rotation("y", math.degrees(x / (P.PD / 2)))
        c = np.array([xc, 0.0, P.Z_PULLEY])
        return G.mat4(R, c - R @ c)
    return np.eye(4)


def printed_instances():
    """[(instance name, part, local->home matrix, group)] for every printed copy."""
    out = []
    for name, spec in S.PARTS.items():
        for k, M in enumerate(spec["copies"]):
            inst = name if len(spec["copies"]) == 1 else f"{name}_{k + 1}"
            group = spec["group"]
            if name == "pulley_flange":
                group = "pulleys_m" if k == 0 else "pulleys_i"
            out.append((inst, name, np.asarray(M, float), group))
    return out


def solids_at(x=0.0, theta=0.0, parts=None, vit=None, include_opt=False):
    """{instance: (solid at this pose, group)} for the v1 machine (build123d, for the clash checks)."""
    parts = parts or S.build(write=False, verbose=False)
    out = {}
    for inst, name, M, group in printed_instances():
        if group.endswith("_opt") and not include_opt:
            continue
        out[inst] = (_moved(parts[name], pose(group, x, theta) @ M), group)
    for name, solid, group, colour, label in (vit or V.items()):
        if group.endswith("_opt") and not include_opt:
            continue
        out[name] = (_moved(solid, pose(group, x, theta)), group)
    return out


def _moved(solid, M):
    from build123d import Location
    M = np.asarray(M, float)
    if np.allclose(M, np.eye(4)):
        return solid
    return solid.moved(Location(_occ_trsf(M)))


def _occ_trsf(M):
    from OCP.gp import gp_Trsf
    t = gp_Trsf()
    t.SetValues(*[float(M[i, j]) for i in range(3) for j in range(4)])
    return t


def mesh_props(tris):
    """(volume mm^3, centroid, second moments [Sxx, Syy, Szz, Sxz] about the origin) of a closed mesh."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    v = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    vol = v.sum()
    cen = (v[:, None] * (a + b + c) / 4.0).sum(0) / vol
    s = a + b + c

    def m2(i, j):
        return (v / 20.0 * (a[:, i] * a[:, j] + b[:, i] * b[:, j] + c[:, i] * c[:, j] + s[:, i] * s[:, j])).sum()
    return vol, cen, dict(xx=m2(0, 0), yy=m2(1, 1), zz=m2(2, 2), xz=m2(0, 2))


def write(parts=None, vit=None, step=True):
    parts = parts or S.build(verbose=False)
    vit = vit or V.items()
    os.makedirs(G.VITAMINS, exist_ok=True)
    from cad import export
    items = []
    for inst, name, M, group in printed_instances():
        spec = S.PARTS[name]
        items.append(dict(name=inst, part=name, kind="printed", file=f"assembly/{name}.stl", matrix=_cm(M),
                          group=group, material=spec["material"], colour=GROUP_COLOURS[spec["material"]],
                          label=spec["role"], qty=len(spec["copies"])))
    for name, solid, group, colour, label in vit:
        export(solid, os.path.join(G.VITAMINS, name + ".stl"))
        items.append(dict(name=name, part=name, kind="vitamin" if name != "belt" else "belt",
                          file=f"vitamins/{name}.stl", matrix=_cm(np.eye(4)), group=group, colour=colour, label=label))
    old = AB.build()
    v0 = [dict(name=n, file=f"as_built/{n}.stl", group=g, colour=c, label=lab) for n, _, g, c, lab in AB.PARTS]
    findings = [dict(id=i, at=list(p), text=t) for i, p, t in AB.FINDINGS]
    bl = H.bolts()
    info = dict(
        units="mm", items=items, bolts=bl, hardware=H.counts(bl), v0=v0, findings=findings,
        layout=dict(z_shaft=P.Z_SHAFT, y_pivot=[P.Y_SHAFT_START, P.Y_SHAFT_END], x_motor=P.X_MOTOR, x_idler=P.X_IDLER,
                    z_pulley=P.Z_PULLEY, pd=P.PD, x_stop=P.X_STOP, x_switch=P.X_SWITCH, x_soft=P.X_SOFT,
                    arm_l=P.ARM_L, y_arm=P.Y_ARM, frame=[P.FRAME_L, P.FRAME_W, P.FRAME_H], z_rod=P.Z_ROD,
                    belt_loop=P.BELT_LOOP, belt_loop_range=list(P.BELT_LOOP_RANGE), belt_open_cut=P.BELT_OPEN_CUT,
                    idler_travel=list(P.IDLER_TRAVEL), z_run_land=P.Z_RUN_LAND))
    with open(G.ASSEMBLY_JSON, "w", newline="\n") as f:
        json.dump(info, f, indent=1)
    if step:
        export_step(parts, vit)
    print(f"wrote {ROOT_REL(G.ASSEMBLY_JSON)}: {len(items)} items, {len(bl)} fasteners, {len(v0)} v0 parts, "
          f"{len(findings)} findings")
    return info


def _cm(M):
    return [round(float(v), 6) for v in np.asarray(M, float).T.reshape(-1)]   # column-major for three.js


def smooth_belt():
    """The belt without teeth (tooth roots to back): for the STEP file and the clash envelope."""
    from build123d import Face, Vector, Wire, extrude
    pts, nrm, _, _ = V.belt_path(step=2.0)
    b = P.BELT
    out = pts + nrm * (b["thick"] - b["tooth_h"])
    inn = pts - nrm * b["tooth_h"]
    ow = Wire.make_polygon([Vector(x, P.Y_BELT - b["width"] / 2, z) for x, z in out], close=True)
    iw = Wire.make_polygon([Vector(x, P.Y_BELT - b["width"] / 2, z) for x, z in inn], close=True)
    return extrude(Face(ow, [iw]), amount=b["width"], dir=(0, 1, 0))


def export_step(parts, vit, path=None):
    """The v1 machine at the home pose as one STEP file, every part named and coloured."""
    from build123d import Color, Compound, export_step as _export
    path = path or os.path.join(G.PARTS_DIR, "inverted_pendulum_v1.step")
    kids = []
    for inst, name, M, group in printed_instances():
        if group.endswith("_opt"):
            continue
        s = _moved(parts[name], M)
        s.label = inst
        s.color = Color(GROUP_COLOURS[S.PARTS[name]["material"]])
        kids.append(s)
    for name, solid, group, colour, label in vit:
        if group.endswith("_opt"):
            continue
        s = smooth_belt() if name == "belt" else solid      # the toothed belt alone is ~15 MB of STEP
        s.label = name
        s.color = Color(colour)
        kids.append(s)
    asm = Compound(children=kids)
    asm.label = "inverted_pendulum_v1"
    _export(asm, path)
    print(f"wrote {ROOT_REL(path)} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    write(step="--no-step" not in sys.argv)

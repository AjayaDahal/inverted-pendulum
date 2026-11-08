"""v0: the machine as photographed (parts/as_built/), approximate, and what is wrong with it.

Sizes of the owner's printed parts are estimated from the photos; positions follow the photos'
latest state (KP08s in line front-to-back on the old plate, motor on the -x back post, idler on
a rod cantilevered from a bracket on the +x back post, a hollow ladder bar hanging from the plate
with a hex key through it as the belt link). The frame, rails and SC8UU are shared with v1.
"""
import os

import numpy as np

import geom as G
import params as P
from cad import box, cyl_y, cyl_z, export

Y_OLD_BELT = -20.0          # belt plane of the old layout (estimated)
Z_OLD_MOTOR, Z_OLD_IDLER = 238.0, 224.0
X_OLD_MOTOR, X_OLD_IDLER = -(P.X_END - 24.0), P.X_BAR_IN - 6.0   # inboard of the end frames' planes
R_OLD = 24.0                # old printed pulleys
Y_OLD_POST_FACE = P.Y_POST - P.EXT / 2   # brackets on the back posts' inner faces


def old_plate():
    p = box(-90, 90, -80, 80, P.Z_PLATE0, P.Z_PLATE0 + 6)
    for x in (-70, 70):
        for y in (-P.Y_ROD, P.Y_ROD):
            for dx in (-9, 9):
                for dy in (-12, 12):
                    p -= cyl_z(2.25, x + dx, y + dy, P.Z_PLATE0 - 1, P.Z_PLATE0 + 7)
    return p


def old_kp08(y):
    k = P.KP08
    z0 = P.Z_PLATE0 + 6
    zc = z0 + k["h"]
    a = k["a"] / 2
    b = box(-k["l"] / 2, k["l"] / 2, y - a, y + a, z0, z0 + k["base_t"]) + box(-11, 11, y - a, y + a, z0, zc)
    b += cyl_y(k["top"] - k["h"], 0, zc, y - a, y + a) + cyl_y(k["ring_od"] / 2, 0, zc, y - 9.5, y + 9.5)
    return b - cyl_y(4.0, 0, zc, y - 12, y + 12)


def old_bar():
    """Hollow bar with a ladder of slots, two screws through a small flange under the plate."""
    y = Y_OLD_BELT
    z0, z1 = Z_OLD_MOTOR + R_OLD - 30.0, P.Z_PLATE0
    b = box(-11, 11, y - 8, y + 8, z0, z1) - box(-8.5, 8.5, y - 5.5, y + 5.5, z0 - 1, z1 - 6)
    b += box(-24, 24, y - 8, y + 8, z1 - 5, z1)
    for k in range(12):
        z = z0 + 8 + 7.5 * k
        b -= box(-6, 6, y - 9, y + 9, z, z + 3)
    return b


def hex_key():
    y = Y_OLD_BELT
    z = Z_OLD_MOTOR + R_OLD - 22.0
    return cyl_y(1.3, 0, z, y - 22, y + 16) + cyl_z(1.3, 0, y - 22, z - 28, z + 1.3)


def old_motor_bracket():
    """L bracket on the -x back post with stacked spacers pushing the motor out to the belt."""
    yb = Y_OLD_POST_FACE
    b = box(-P.X_BAR_IN - 4, -P.X_BAR_IN + 30, yb - 6, yb, Z_OLD_MOTOR - 30, Z_OLD_MOTOR + 26)
    for dz in (-15.5, 15.5):
        b += box(X_OLD_MOTOR - 8, X_OLD_MOTOR + 8, Y_OLD_BELT + 14 + 40, yb - 6, Z_OLD_MOTOR + dz - 5, Z_OLD_MOTOR + dz + 5)
    return b


def old_motor():
    m = P.NEMA17
    a = m["side"] / 2
    yf = Y_OLD_BELT + 14.0
    body = box(X_OLD_MOTOR - a, X_OLD_MOTOR + a, yf, yf + m["length"], Z_OLD_MOTOR - a, Z_OLD_MOTOR + a)
    return body + cyl_y(2.5, X_OLD_MOTOR, Z_OLD_MOTOR, yf - m["shaft_len"], yf)


def old_pulley(x, z, both=False):
    """20-tooth 8M, printed. The motor's has one flange (motor side); the idler's has two
    (photos of 2026-11-08)."""
    y = Y_OLD_BELT
    h = P.TOOTH_W / 2
    p = cyl_y(R_OLD - 1.0, x, z, y - h, y + h) + cyl_y(R_OLD + 5.0, x, z, y + h, y + h + 2)
    if both:
        p += cyl_y(R_OLD + 5.0, x, z, y - h - 2, y - h)
    return p - cyl_y(2.0 if x < 0 else 2.6, x, z, y - h - 3, y + h + 3)


def old_idler_bracket():
    """Plate with a row of holes on the +x back post; the axle is a thin rod cantilevered from it."""
    yb = Y_OLD_POST_FACE
    b = box(P.X_BAR_IN - 40, P.X_BAR_IN, yb - 5, yb, Z_OLD_IDLER - 12, Z_OLD_IDLER + 12)
    for k in range(7):
        b -= cyl_y(2.2, P.X_BAR_IN - 36 + 6 * k, Z_OLD_IDLER, yb - 6, yb + 1)
    return b


def old_idler_rod():
    """Two thin rods (about 1.7 mm) taped together, held at one end by the bracket."""
    y0, y1 = Y_OLD_BELT - 25, Y_OLD_POST_FACE - 2.0
    return (cyl_y(0.85, X_OLD_IDLER - 0.8, Z_OLD_IDLER, y0, y1)
            + cyl_y(0.85, X_OLD_IDLER + 0.8, Z_OLD_IDLER, y0, y1))


def old_belt():
    """The old loop without teeth: the pulleys sit at different heights, so the runs slope."""
    from build123d import Face, Vector, Wire, extrude
    t, w = P.BELT["thick"], P.BELT["width"]
    outer_pts, inner_pts = [], []
    for (x, z, a0) in ((X_OLD_IDLER, Z_OLD_IDLER, -90), (X_OLD_MOTOR, Z_OLD_MOTOR, 90)):
        for a in np.linspace(a0, a0 + 180, 40):
            c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
            outer_pts.append((x + (R_OLD + t) * c, z + (R_OLD + t) * s))
            inner_pts.append((x + R_OLD * c, z + R_OLD * s))
    ow = Wire.make_polygon([Vector(x, Y_OLD_BELT - w / 2, z) for x, z in outer_pts], close=True)
    iw = Wire.make_polygon([Vector(x, Y_OLD_BELT - w / 2, z) for x, z in inner_pts], close=True)
    return extrude(Face(ow, [iw]), amount=w, dir=(0, 1, 0))


def old_switch_arm():
    x, y = -P.X_END, P.Y_POST - 25.0
    return (box(x - 7, x + 7, y - 7, y + 7, P.FRAME_H, P.FRAME_H + 20) + cyl_z(4, x, y, P.FRAME_H + 20, P.FRAME_H + 45)
            + box(x - 6, x + 30, y - 20, y, P.FRAME_H + 40, P.FRAME_H + 46))


def old_wedge():
    """The black wedge with a pocket on the +x front post (purpose unknown, kept)."""
    from cad import prism_xz
    y0, y1 = -P.Y_POST - 10, -P.Y_POST + 10
    w = prism_xz([(P.X_BAR_OUT, 140), (P.X_BAR_OUT + 45, 140), (P.X_BAR_OUT, 215)], y0, y1)
    return w - box(P.X_BAR_OUT + 4, P.X_BAR_OUT + 22, y0 + 3, y1 - 3, 146, 170)


# name, builder, group, colour, label
PARTS = [
    ("old_plate", old_plate, "cart", "#2b2d30", "old carriage plate (printed)"),
    ("old_kp08_front", lambda: old_kp08(12.0), "cart", "#3a3d42", "KP08, old position"),
    ("old_kp08_rear", lambda: old_kp08(60.0), "cart", "#3a3d42", "KP08, old position"),
    ("old_bar", old_bar, "cart", "#22252a", "old belt link: hollow ladder bar"),
    ("hex_key", hex_key, "cart", "#c0c4c9", "hex key used as the belt pin"),
    ("old_motor_bracket", old_motor_bracket, "frame", "#8e959c", "old motor bracket + spacers on the back post"),
    ("old_motor", old_motor, "frame", "#26282b", "NEMA 17 (old position)"),
    ("old_motor_pulley", lambda: old_pulley(X_OLD_MOTOR, Z_OLD_MOTOR), "frame", "#2b2d30", "old pulley, one flange"),
    ("old_idler_pulley", lambda: old_pulley(X_OLD_IDLER, Z_OLD_IDLER, both=True), "frame", "#2b2d30",
     "old idler, 20-tooth 8M, two flanges"),
    ("old_idler_bracket", old_idler_bracket, "frame", "#22252a", "old idler bracket: row of holes"),
    ("old_idler_rod", old_idler_rod, "frame", "#4a4e54", "old idler axle: two thin rods taped together, held at one end"),
    ("old_belt", old_belt, "frame", "#1d1f22", "belt (old run)"),
    ("old_switch_arm", old_switch_arm, "frame", "#22252a", "old limit-switch arm"),
    ("old_wedge", old_wedge, "frame", "#22252a", "wedge part (kept as is)"),
]

# What the audit found (REPORT.md has the reasoning): id, where (for the viewer's marker), title.
FINDINGS = [
    ("A1", (X_OLD_IDLER, 60.0, Z_OLD_IDLER), "Idler axle: two ~1.7 mm rods taped together, held at one end ~140 mm from its bracket: belt tension bends and tilts them, so the belt walks"),
    ("A2", (P.X_BAR_IN - 20, Y_OLD_POST_FACE - 2.0, Z_OLD_IDLER + 14), "Idler position set by a row of holes: tension only in 6 mm steps, no lock, no squaring"),
    ("A3", (X_OLD_MOTOR, 40.0, Z_OLD_MOTOR + 25), "Motor and idler each located from a different post with spacers: nothing puts both pulleys and the clamp in one plane"),
    ("A4", (X_OLD_MOTOR, Y_OLD_BELT, Z_OLD_MOTOR - 30), "The motor pulley has one flange, and the two pulleys sit at different heights, so the runs slope"),
    ("A5", (0.0, Y_OLD_BELT - 20, Z_OLD_MOTOR), "Belt link: hollow ladder bar and a hex key through a slot. No teeth engaged: it slips and has backlash"),
    ("A6", (0.0, 45.0, P.Z_PLATE0 + 40), "Pivot over the middle of the cart: a pendulum there hangs inside the frame, cannot pass the plate or rails, so it cannot swing up"),
    ("A7", (0.0, 70.0, P.Z_PLATE0 + 20), "No shaft, hub, arm or angle-sensor mount yet"),
    ("A8", (-P.X_END, P.Y_POST - 25.0, P.FRAME_H + 50), "One limit switch on a separate arm; no hard stops: the SC8UU blocks run into the SK8 supports"),
    ("A9", (0.0, P.FRAME_W / 2 + 40.0, 60.0), "Electronics and leads loose on the desk; no strain relief on the moving cart"),
]


def build(write=True):
    out = {}
    os.makedirs(G.ASBUILT, exist_ok=True)
    for name, fn, group, colour, label in PARTS:
        s = fn()
        out[name] = s
        if write:
            export(s, os.path.join(G.ASBUILT, name + ".stl"))
    return out


if __name__ == "__main__":
    for n, s in build().items():
        bb = s.bounding_box()
        print(f"{n:18s} vol {s.volume / 1000:7.1f} cm3  x {bb.min.X:7.1f}..{bb.max.X:7.1f}  y {bb.min.Y:7.1f}..{bb.max.Y:7.1f}"
              f"  z {bb.min.Z:6.1f}..{bb.max.Z:6.1f}")

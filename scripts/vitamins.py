"""The owner's hardware, modelled for the assembly, the clash checks and the viewer: the 2020/2040
frame, rods, SK8 and SC8UU, KP08 pillow blocks, NEMA 17, pivot shaft, sensors, limit switches,
boards and the HTD belt. Catalogue sizes; envelopes where the detail does not matter.

Each item is built in the assembly frame at the home pose (cart at x = 0, pendulum upright).
`items()` lists them with their motion group, colour and label.
"""
import math

import numpy as np
from build123d import Face, Pos, Rot, Vector, Wire, extrude

import params as P
from cad import box, cyl_x, cyl_y, cyl_z, hex_z, prism_yz, slot_z

STEEL, ALU, BLACK, DARK = "#9aa3ad", "#c7ccd2", "#26282b", "#3a3d42"


# ---------------------------------------------------------------- frame
def _profile_cuts(nx, ny, length, axis):
    """Slots (6.2 x 6 deep) on every 20 mm module of every face, plus the centre bores, of an
    nx x ny module profile running along `axis` from 0 to length (local, centred section)."""
    w, h = nx * P.EXT, ny * P.EXT
    cuts = []
    for i in range(nx):
        u = -w / 2 + P.EXT * (i + 0.5)
        cuts.append(((u, h / 2 - 3.0), (P.SLOT, 6.01)))
        cuts.append(((u, -h / 2 + 3.0), (P.SLOT, 6.01)))
    for j in range(ny):
        v = -h / 2 + P.EXT * (j + 0.5)
        cuts.append(((w / 2 - 3.0, v), (6.01, P.SLOT)))
        cuts.append(((-w / 2 + 3.0, v), (6.01, P.SLOT)))
    return cuts


def extrusion(nx, ny, a0, a1, axis, c1, c2):
    """A 20-series profile, nx x ny modules, from a0 to a1 along `axis`, section centred at
    (c1, c2) in the other two axes (x->(y, z), y->(x, z), z->(x, y))."""
    w, h = nx * P.EXT, ny * P.EXT
    lo, hi = min(a0, a1), max(a0, a1)

    def blk(u0, u1, v0, v1):
        if axis == "x":
            return box(lo, hi, c1 + u0, c1 + u1, c2 + v0, c2 + v1)
        if axis == "y":
            return box(c1 + u0, c1 + u1, lo, hi, c2 + v0, c2 + v1)
        return box(c1 + u0, c1 + u1, c2 + v0, c2 + v1, lo, hi)

    s = blk(-w / 2, w / 2, -h / 2, h / 2)
    for (u, v), (du, dv) in _profile_cuts(nx, ny, hi - lo, axis):
        s -= blk(u - du / 2, u + du / 2, v - dv / 2, v + dv / 2)
    return s


def frame_parts():
    """[(name, solid)]: 4 posts (2020), top end bars (2040 on edge) and bottom end bars between
    them, and the two long bottom members (2020)."""
    out = []
    y_in = P.Y_POST - P.EXT / 2
    for sx in (-1, 1):
        end = "mp"[sx > 0]
        for sy in (-1, 1):
            out.append((f"post_{end}{'fb'[sy > 0]}", extrusion(1, 1, 0, P.FRAME_H, "z", sx * P.X_END, sy * P.Y_POST)))
        out.append((f"top_bar_{end}", extrusion(1, 2, -y_in, y_in, "y", sx * P.X_END, sum(P.Z_BAR) / 2)))
        out.append((f"bottom_bar_{end}", extrusion(1, 1, -y_in, y_in, "y", sx * P.X_END, P.EXT / 2)))
    x_in = P.X_END - P.EXT / 2
    for sy in (-1, 1):
        out.append((f"long_{'fb'[sy > 0]}", extrusion(1, 1, -x_in, x_in, "x", sy * P.Y_POST, P.EXT / 2)))
    return out


# ---------------------------------------------------------------- linear guide
def rod(y):
    return cyl_x(P.ROD_D / 2, y, P.Z_ROD, -P.ROD_L / 2, P.ROD_L / 2)


def sk8(x, y):
    """SK8 rod support on the top end bar, rod along x."""
    s = P.SK8
    base = box(x - s["t"] / 2, x + s["t"] / 2, y - s["w"] / 2, y + s["w"] / 2, P.FRAME_H, P.FRAME_H + 7)
    up = prism_yz([(y - 10.5, P.FRAME_H + 7), (y + 10.5, P.FRAME_H + 7), (y + 10.5, P.FRAME_H + s["h_total"] - 4),
                   (y + 6.5, P.FRAME_H + s["h_total"]), (y - 6.5, P.FRAME_H + s["h_total"]),
                   (y - 10.5, P.FRAME_H + s["h_total"] - 4)], x - s["t"] / 2, x + s["t"] / 2)
    body = base + up - cyl_x(P.ROD_D / 2, y, P.Z_ROD, x - 8, x + 8)
    for sy in (-1, 1):
        body -= cyl_z(2.75, x, y + sy * s["bolt"] / 2, P.FRAME_H - 1, P.FRAME_H + 8)
    return body


def sc8uu(x, y):
    """SC8UU block hanging under the carriage plate: mounting face at Z_PLATE0, rod along x."""
    s = P.SC8UU
    z1 = P.Z_PLATE0
    b = box(x - s["l"] / 2, x + s["l"] / 2, y - s["w"] / 2, y + s["w"] / 2, z1 - s["h"], z1)
    b -= cyl_x(P.ROD_D / 2 + 0.3, y, P.Z_ROD, x - 16, x + 16)
    for sx in (-1, 1):
        for sy in (-1, 1):
            b -= cyl_z(1.7, x + sx * s["hole_l"] / 2, y + sy * s["hole_w"] / 2, z1 - 8, z1 + 0.1)
    return b


# ---------------------------------------------------------------- pivot
def kp08(y):
    """KP08 pillow block at (0, y) on the pivot bridge, bore along y at Z_SHAFT."""
    k = P.KP08
    z0 = P.Z_BRIDGE1
    a = k["a"] / 2
    base = box(-k["l"] / 2, k["l"] / 2, y - a, y + a, z0, z0 + k["base_t"])
    web = box(-11, 11, y - a, y + a, z0, P.Z_SHAFT)
    ring = cyl_y(k["top"] - k["h"], 0, P.Z_SHAFT, y - a, y + a)
    insert = cyl_y(k["ring_od"] / 2, 0, P.Z_SHAFT, y - k["ring_w"] / 2, y + k["ring_w"] / 2)
    body = base + web + ring + insert - cyl_y(P.SHAFT_D / 2, 0, P.Z_SHAFT, y - 12, y + 12)
    for sx in (-1, 1):
        body -= slot_z(k["slot"] / 2, sx * (k["j"] / 2 - 1.5), y, sx * (k["j"] / 2 + 1.5), y, z0 - 1, z0 + 8)
    return body


def shaft():
    return cyl_y(P.SHAFT_D / 2, 0, P.Z_SHAFT, P.Y_SHAFT_START, P.Y_SHAFT_END)


def magnet():
    m = P.AS5600
    return cyl_y(m["magnet_d"] / 2, 0, P.Z_SHAFT, P.Y_MAGNET - m["magnet_t"], P.Y_MAGNET)


def as5600_board():
    """AS5600 module on the sensor tower's front face, chip towards the magnet."""
    m = P.AS5600
    yb = P.Y_TOWER - m["standoff"]
    pcb = box(-m["board"] / 2, m["board"] / 2, yb - m["pcb"], yb, P.Z_SHAFT - m["board"] / 2, P.Z_SHAFT + m["board"] / 2)
    chip = box(-2.5, 2.5, yb - m["pcb"] - m["chip"], yb - m["pcb"], P.Z_SHAFT - 2.0, P.Z_SHAFT + 2.0)
    header = box(-8.9, 8.9, yb - m["pcb"] - 2.5, yb - m["pcb"], P.Z_SHAFT - m["board"] / 2 + 0.5,
                 P.Z_SHAFT - m["board"] / 2 + 3.0)
    return pcb + chip + header


def lpd3806():
    """Optional 600 P/R optical encoder on the sensor tower's back face (y0 = its mounting face)."""
    e = P.LPD3806
    y0 = P.Y_TOWER + P.TOWER_T
    body = cyl_y(e["d"] / 2, 0, P.Z_SHAFT, y0, y0 + e["length"])
    boss = cyl_y(e["boss_d"] / 2, 0, P.Z_SHAFT, y0 - e["boss_h"], y0)
    sh = cyl_y(e["shaft"] / 2, 0, P.Z_SHAFT, y0 - e["boss_h"] - e["shaft_len"], y0 - e["boss_h"])
    return body + boss + sh


# ---------------------------------------------------------------- motor
def nema17():
    """Motor on the motor mount: face at Y_MOTOR_FACE, body behind (+y), shaft forward (-y)."""
    m = P.NEMA17
    yf, a, c = P.Y_MOTOR_FACE, m["side"] / 2, m["chamfer"]
    oct_pts = [(-a + c, -a), (a - c, -a), (a, -a + c), (a, a - c), (a - c, a), (-a + c, a), (-a, a - c), (-a, -a + c)]
    face = Face(Wire.make_polygon([Vector(P.X_MOTOR + u, yf, P.Z_PULLEY + v) for u, v in oct_pts], close=True))
    body = extrude(face, amount=m["length"], dir=(0, 1, 0))
    boss = cyl_y(m["boss"] / 2, P.X_MOTOR, P.Z_PULLEY, yf - m["boss_h"], yf)
    sh = cyl_y(m["shaft"] / 2, P.X_MOTOR, P.Z_PULLEY, yf - m["shaft_len"], yf)
    flat = box(P.X_MOTOR + m["shaft"] / 2 - m["flat"], P.X_MOTOR + 3, yf - m["shaft_len"] - 1, yf - 9,
               P.Z_PULLEY - 3, P.Z_PULLEY + 3)            # D flat facing +x, where the pulley's set screw is
    out = body + boss + sh - flat
    for sx in (-1, 1):
        for sz in (-1, 1):
            out -= cyl_y(1.5, P.X_MOTOR + sx * m["hole"] / 2, P.Z_PULLEY + sz * m["hole"] / 2, yf - 0.1, yf + 4.5)
    return out


# ---------------------------------------------------------------- switches and electronics
def endstop_geometry(x_sign):
    """Where the endstop board sits: its inboard end, the switch body, the lever's tip (x values
    for the +x end; mirror for -x). The roller meets the plate's end face at X_SWITCH."""
    e = P.ENDSTOP
    x_body = P.X_STOP + P.PLATE_X + 2.0          # switch body 2 mm beyond the plate at the stop
    x_tip = P.X_SWITCH + P.PLATE_X               # roller contact
    z0 = P.Z_PLATE0 - 4.0                        # PCB underside
    return dict(x_pcb=(x_body - 1.0, x_body - 1.0 + e["pcb"][0]), x_body=(x_body, x_body + e["sw"][0]),
                x_tip=x_tip, z0=z0, z_lever=z0 + e["pcb"][2] + e["sw"][2])


def endstop(x_sign):
    """Mechanical endstop board lying on its switch mount, lever towards the cart."""
    e = P.ENDSTOP
    g = endstop_geometry(x_sign)
    t = e["pcb"][2]
    y0, y1 = P.Y_SWITCH - e["pcb"][1] / 2, P.Y_SWITCH + e["pcb"][1] / 2

    def bx(x0, x1, ya, yb, z0, z1):
        a, b = x_sign * x0, x_sign * x1
        return box(min(a, b), max(a, b), ya, yb, z0, z1)

    pcb = bx(*g["x_pcb"], y0, y1, g["z0"], g["z0"] + t)
    sw = bx(*g["x_body"], P.Y_SWITCH - e["sw"][1] / 2, P.Y_SWITCH + e["sw"][1] / 2, g["z0"] + t, g["z_lever"])
    lever = bx(g["x_tip"], g["x_body"][1] - 1.5, P.Y_SWITCH - 2, P.Y_SWITCH + 2, g["z_lever"], g["z_lever"] + 0.6)
    roller = cyl_y(1.6, x_sign * (g["x_tip"] + 1.6), g["z_lever"] - 1.0, P.Y_SWITCH - 2, P.Y_SWITCH + 2)
    plug = bx(g["x_pcb"][1] - 9.0, g["x_pcb"][1] - 1.0, P.Y_SWITCH - 5, P.Y_SWITCH + 5, g["z0"] + t, g["z0"] + t + 6)
    return pcb + sw + lever + roller + plug


def tray_boards():
    """[(name, solid, colour, label)] on the electronics tray behind the frame."""
    y0 = P.FRAME_W / 2 + 12.0
    z0 = P.TRAY["t"]
    drv = box(-70, -20, y0 + 20, y0 + 70, z0 + 5, z0 + 6.6) + box(-62, -28, y0 + 30, y0 + 60, z0 + 6.6, z0 + 18)
    ctl = box(5, 60, y0 + 30, y0 + 58, z0 + 5, z0 + 6.6) + box(12, 50, y0 + 34, y0 + 54, z0 + 6.6, z0 + 13)
    return [("driver_board", drv, "#1f5fbf", "stepper driver carrier (A4988 / DRV8825)"),
            ("controller", ctl, "#127a4a", "controller (Arduino Uno / Nano or ESP32)")]


# ---------------------------------------------------------------- belt (HTD), as a mesh
def belt_path(x_motor=P.X_MOTOR, x_idler=P.X_IDLER, z=P.Z_PULLEY, r=P.R_TIP, n_arc=160, step=0.4):
    """Points along the belt's land (tooth-side face) loop and the outward normal at each, by arc
    length: upper run motor -> idler, round the idler, lower run back, round the motor pulley."""
    pts, nrm = [], []
    run = x_idler - x_motor
    segs = [("line", (x_motor, z + r), (1, 0), run, (0, 1)),
            ("arc", (x_idler, z), 90.0, -180.0),
            ("line", (x_idler, z - r), (-1, 0), run, (0, -1)),
            ("arc", (x_motor, z), -90.0, -180.0)]
    for seg in segs:
        if seg[0] == "line":
            _, p0, d, length, n = seg
            k = max(2, int(length / step))
            for i in range(k):
                t = length * i / k
                pts.append((p0[0] + d[0] * t, p0[1] + d[1] * t))
                nrm.append(n)
        else:
            _, c, a0, da = seg
            k = max(8, int(abs(math.radians(da)) * r / step))
            for i in range(k):
                a = math.radians(a0 + da * i / k)
                pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
                nrm.append((math.cos(a), math.sin(a)))
    pts, nrm = np.array(pts), np.array(nrm)
    seg_len = np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg_len)[:-1]])
    return pts, nrm, s, float(seg_len.sum())


def belt_solid(x_idler=P.X_IDLER):
    """The belt as one solid: back surface outside, land plus HTD-like teeth inside. A tooth sits
    centred on x = 0 of the upper run, where the clamp's seats are."""
    b = P.BELT
    pts, nrm, s, total = belt_path(x_idler=x_idler)
    back = pts + nrm * (b["thick"] - b["tooth_h"])
    s0 = -P.X_MOTOR          # arc length of x = 0 on the upper run
    ph = ((s - s0) / b["pitch"] + 0.5) % 1.0 - 0.5          # -0.5..0.5 within a pitch, 0 = tooth centre
    half = 1.75 / b["pitch"]
    h = np.where(np.abs(ph) < half, b["tooth_h"] * np.cos(np.clip(ph / half, -1, 1) * math.pi / 2) ** 0.6, 0.0)
    inner = pts - nrm * h[:, None]
    outer_w = Wire.make_polygon([Vector(x, -b["width"] / 2 + P.Y_BELT, zz) for x, zz in back[::3]], close=True)
    inner_w = Wire.make_polygon([Vector(x, -b["width"] / 2 + P.Y_BELT, zz) for x, zz in inner], close=True)
    face = Face(outer_w, [inner_w])
    return extrude(face, amount=b["width"], dir=(0, 1, 0)), total


def belt_loop_length(x_idler=P.X_IDLER):
    """Pitch-line length of the loop."""
    return 2 * (x_idler - P.X_MOTOR) + math.pi * P.PD


# ---------------------------------------------------------------- registry
def items(belt=True):
    """[(name, solid, group, colour, label)] of the owner's hardware at the home pose (belt=False
    leaves out the toothed belt, slow to build)."""
    out = [(n, s, "frame", ALU, "2020 / 2040 aluminium profile") for n, s in frame_parts()]
    for sy in (-1, 1):
        out.append((f"rod_{'fb'[sy > 0]}", rod(sy * P.Y_ROD), "frame", STEEL, "8 mm rod"))
        for sx in (-1, 1):
            out.append((f"sk8_{'mp'[sx > 0]}{'fb'[sy > 0]}", sk8(sx * P.X_END, sy * P.Y_ROD), "frame", ALU, "SK8 rod support"))
            out.append((f"sc8uu_{'mp'[sx > 0]}{'fb'[sy > 0]}", sc8uu(sx * P.BEARING_X, sy * P.Y_ROD), "cart", ALU,
                        "SC8UU bearing block"))
    out.append(("kp08_front", kp08(P.Y_KP_F), "cart", DARK, "KP08 pillow block"))
    out.append(("kp08_rear", kp08(P.Y_KP_R), "cart", DARK, "KP08 pillow block"))
    out.append(("pivot_shaft", shaft(), "pendulum", STEEL, f"8 mm pivot shaft, {P.SHAFT_L:.0f} mm"))
    out.append(("magnet", magnet(), "pendulum", "#b0473a", "6 x 2.5 mm diametric magnet"))
    out.append(("as5600", as5600_board(), "cart", "#5b2a86", "AS5600 magnetic encoder board"))
    out.append(("lpd3806", lpd3806(), "cart_opt", DARK, "optional: 600 P/R optical encoder"))
    out.append(("nema17", nema17(), "frame", BLACK, "NEMA 17 stepper"))
    for sx in (-1, 1):
        out.append((f"endstop_{'mp'[sx > 0]}", endstop(sx), "frame", "#b8202a", "mechanical endstop"))
    for n, s, c, lab in tray_boards():
        out.append((n, s, "frame", c, lab))
    if belt:
        b, _ = belt_solid()
        out.append(("belt", b, "belt", "#1d1f22", f"HTD {P.BELT['pitch']:.0f}M belt, {P.BELT['width']:.0f} mm"))
    return out

"""The printed parts (v1), built with build123d in the assembly frame at the home pose (cart at
x = 0, pendulum upright), and the registry the other scripts read: material, copies and their
placements, print orientation, motion group, the bolts each part takes.

Run on its own to write parts/assembly/<part>.stl (first copy, assembly frame).
"""
import math
import os
import sys

import numpy as np
from build123d import Pos, Rot

import geom as G
import params as P
from cad import (box, cyl_x, cyl_y, cyl_z, export, hex_x, hex_y, hex_z, prism_xy, prism_xz, prism_yz,
                 pulley_teeth_face, rack_grooves, slot_x, slot_y, slot_z)
from build123d import extrude

F = P.FIT
NUT3, NUT5 = P.NUT["M3"], P.NUT["M5"]


def _chamfered_rect(x0, x1, y0, y1, c):
    return [(x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c)]


# ================================================================== carriage
SC_HOLES = [(sx * P.BEARING_X + dx * P.SC8UU["hole_l"] / 2, sy * P.Y_ROD + dy * P.SC8UU["hole_w"] / 2)
            for sx in (-1, 1) for sy in (-1, 1) for dx in (-1, 1) for dy in (-1, 1)]
BRIDGE_BOLTS = [(sx * (P.BRIDGE_X + 7.0), y) for sx in (-1, 1) for y in P.BRIDGE_BOLT_Y]
CLAMP_BOLTS = [(sx * 25.0, sy * 9.0) for sx in (-1, 1) for sy in (-1, 1)]
CB3 = 3.2                                  # M3 head counterbore depth
CB4 = 4.2                                  # M4 head counterbore depth
MARK = 0.6                                 # depth of the orientation marks in the plate's top face


def carriage_plate():
    """Rides on the four SC8UU blocks (holes slotted +-SC_SLOT in y, for the rods' spacing); the
    pivot bridge bolts on top, the belt clamp underneath, both on nuts in pockets. Nearly square, so
    its top face is marked: a line over each rod and an arrow to the front edge (REPORT R12)."""
    z0, z1 = P.Z_PLATE0, P.Z_PLATE1
    p = prism_xy(_chamfered_rect(-P.PLATE_X, P.PLATE_X, -P.PLATE_Y, P.PLATE_Y, 6.0), z0, z1)
    for x, y in SC_HOLES:
        p -= slot_z(P.D_M4 / 2, x, y - P.SC_SLOT, x, y + P.SC_SLOT, z0 - 1, z1 + 1)
        p -= slot_z(P.HEAD["M4"][0] / 2 + F, x, y - P.SC_SLOT, x, y + P.SC_SLOT, z1 - CB4, z1 + 1)
    for x, y in BRIDGE_BOLTS:
        p -= cyl_z(P.D_M5 / 2, x, y, z0 - 1, z1 + 1)
        p -= hex_z(NUT5[0] + 0.3, x, y, z0 - 1, z0 + NUT5[1] + 0.5)
    for x, y in CLAMP_BOLTS:
        p -= cyl_z(P.D_M3 / 2, x, y, z0 - 1, z1 + 1)
        p -= cyl_z(P.HEAD["M3"][0] / 2 + F, x, y, z1 - CB3, z1 + 1)
    for sx in (-1, 1):                     # zip-tie bridges for the sensor cable at the back edge
        p -= box(sx * 8 - 2, sx * 8 + 2, P.PLATE_Y - 9, P.PLATE_Y - 6, z0 - 1, z1 + 1)
    p -= box(-10, 10, P.PLATE_Y - 9, P.PLATE_Y - 6, z0 - 1, z0 + 3)
    x_line = P.BEARING_X - P.SC8UU["hole_l"] / 2 - P.HEAD["M4"][0] / 2 - F - 5.0
    for sy in (-1, 1):
        p -= box(-x_line, x_line, sy * P.Y_ROD - 0.75, sy * P.Y_ROD + 0.75, z1 - MARK, z1 + 1)
    p -= prism_xy([(-8.0, -P.Y_ROD - 3.0), (8.0, -P.Y_ROD - 3.0), (0.0, -P.Y_ROD - 15.0)], z1 - MARK, z1 + 1)
    return p


def bridge_slab_outline():
    y0, y1 = P.Y_BRIDGE
    return [(-P.BRIDGE_X, y0), (P.BRIDGE_X, y0), (P.BRIDGE_X, y1 + 12.0), (20.0, y1 + 12.0), (20.0, y1),
            (-20.0, y1), (-20.0, y1 + 12.0), (-P.BRIDGE_X, y1 + 12.0)]


def pivot_bridge():
    """Carries both KP08s in line, the front one over the plate's front edge so the pendulum hangs
    in front of the frame, and the sensor tower behind the rear one (AS5600 adapter in front of
    it, or a 600 P/R encoder behind it). Side flanges slotted +-BRIDGE_SLIDE in y."""
    z0, z1 = P.Z_PLATE1, P.Z_BRIDGE1
    b = prism_xy(bridge_slab_outline(), z0, z1)
    fl_t = 6.0
    for sx in (-1, 1):
        x0, x1 = sorted((sx * P.BRIDGE_X, sx * (P.BRIDGE_X + 14.0)))
        b += box(x0, x1, P.BRIDGE_BOLT_Y[0] - P.BRIDGE_SLIDE - 9.0, P.BRIDGE_BOLT_Y[1] + P.BRIDGE_SLIDE + 9.0,
                 z0, z0 + fl_t)
    for x, y in BRIDGE_BOLTS:
        b -= slot_z(P.D_M5 / 2, x, y - P.BRIDGE_SLIDE, x, y + P.BRIDGE_SLIDE, z0 - 1, z0 + fl_t + 1)
    for y in (P.Y_KP_F, P.Y_KP_R):        # KP08 bolts, nuts in pockets from below
        for sx in (-1, 1):
            b -= cyl_z(P.D_M5 / 2, sx * P.KP08["j"] / 2, y, z0 - 1, z1 + 1)
            b -= hex_z(NUT5[0] + 0.3, sx * P.KP08["j"] / 2, y, z0 - 1, z0 + 6.0, turn=90)
    # sensor tower
    yt0, yt1 = P.Y_TOWER, P.Y_TOWER + P.TOWER_T
    zt1 = P.Z_SHAFT + 23.0
    tower = box(-24.0, 24.0, yt0, yt1, z1 - 0.01, zt1)
    for sx in (-1, 1):                     # gussets beside the encoder body
        x0, x1 = sorted((sx * 20.6, sx * 24.0))
        tower += prism_yz([(yt1 - 0.01, z1), (yt1 + 12.0, z1), (yt1 - 0.01, zt1 - 6.0)], x0, x1)
    b += tower
    # window: teardrop (prints without support), takes the encoder's boss or the AS5600's back
    r = P.LPD3806["boss_d"] / 2 + 0.6
    b -= cyl_y(r, 0, P.Z_SHAFT, yt0 - 1, yt1 + 1)
    b -= prism_xz([(-r * math.cos(math.radians(45)), P.Z_SHAFT + r * math.sin(math.radians(45))),
                   (r * math.cos(math.radians(45)), P.Z_SHAFT + r * math.sin(math.radians(45))),
                   (0, P.Z_SHAFT + r * math.sqrt(2))], yt0 - 1, yt1 + 1)
    for a in (30.0, 150.0, 270.0):        # LPD3806: 3 x M3 on a 28-32 mm circle
        u, v = math.cos(math.radians(a)), math.sin(math.radians(a))
        r0, r1 = P.LPD3806["pcd"][0] / 2, P.LPD3806["pcd"][1] / 2
        b -= slot_y(P.D_M3 / 2, r0 * u, P.Z_SHAFT + r0 * v, r1 * u, P.Z_SHAFT + r1 * v, yt0 - 1, yt1 + 1)
    for x, z in AS_MOUNT_HOLES:            # AS5600 adapter: 2 x M3, nuts on the tower's back
        b -= cyl_y(P.D_M3 / 2, x, z, yt0 - 1, yt1 + 1)
        b -= hex_y(NUT3[0] + 0.3, x, z, yt1 - NUT3[1] - 0.3, yt1 + 1)
    return b


AS_MOUNT_HOLES = [(-16.0, P.Z_SHAFT - 6.0), (16.0, P.Z_SHAFT - 6.0)]


def as5600_mount():
    """Adapter plate on the tower's front face: the AS5600 board on four raised slotted pads (M2.5
    or M3 into the board's corner holes, 18-26 mm apart), its chip on the shaft axis."""
    m = P.AS5600
    t = 3.0
    y1 = P.Y_TOWER
    y0 = y1 - t
    zc = P.Z_SHAFT
    a = box(-22.0, 22.0, y0, y1, P.Z_BRIDGE1 + 0.5, zc + 16.0)
    pads = None
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        u, v = math.cos(ang), math.sin(ang)
        pad = slot_y(3.4, 9.5 * u, zc + 9.5 * v, 13.5 * u, zc + 13.5 * v, y0 - (m["standoff"] - t), y0 + 0.01)
        pads = pad if pads is None else pads + pad
    a += pads
    for k in range(4):
        ang = math.radians(45 + 90 * k)
        u, v = math.cos(ang), math.sin(ang)
        a -= slot_y(1.5, 9.5 * u, zc + 9.5 * v, 13.5 * u, zc + 13.5 * v, y0 - 5, y1 + 1)
    a -= cyl_y(6.0, 0, zc, y0 - 5, y1 + 1)
    for x, z in AS_MOUNT_HOLES:
        a -= cyl_y(P.D_M3 / 2, x, z, y0 - 5, y1 + 1)
        a -= cyl_y(P.HEAD["M3"][0] / 2 + F, x, z, y0 - 5, y0 + 1.0)
    return a


# ================================================================== belt clamp (drop clamp)
def _clamp_levels():
    c = P.CLAMP
    z_ceil = P.Z_RUN_BACK                          # presses the belt's back
    z_side = P.Z_RUN_TIPS - 3.5                    # side walls' bottom, below the teeth
    z_jaw0 = z_side - 0.6 - c["jaw_base"]          # jaw base underside (0.6 mm to take up)
    return z_ceil, z_side, z_jaw0


def _jaw_nut_z():
    """The face of each jaw screw's nut slot towards the jaw, which the nut bears on: on a layer
    boundary, as the clamp prints upside down (its top, z = Z_PLATE0, on the bed)."""
    _, z_side, _ = _clamp_levels()
    return P.Z_PLATE0 - math.ceil((P.Z_PLATE0 - (z_side + 3.8)) / P.LAYER - 1e-6) * P.LAYER


def belt_clamp():
    """Stiff box column from the plate down to the upper run. The belt (open ends or a closed
    loop) lies in a channel 1 mm wider than it, under a flat ceiling; the jaw underneath seats its
    teeth."""
    c = P.CLAMP
    z_ceil, z_side, _ = _clamp_levels()
    fx, fy, ft = c["flange"]
    z_top = P.Z_PLATE0
    seat_top = z_ceil + 6.0
    flare = 15.0
    body = box(-fx / 2, fx / 2, -fy / 2, fy / 2, z_top - ft, z_top)
    col = box(-c["col_x"] / 2, c["col_x"] / 2, -c["col_y"] / 2, c["col_y"] / 2, seat_top + flare - 0.01, z_top - ft + 0.01)
    col -= box(-c["col_x"] / 2 + c["wall"], c["col_x"] / 2 - c["wall"], -c["col_y"] / 2 + c["wall"],
               c["col_y"] / 2 - c["wall"], seat_top + flare + 2.0, z_top - ft - 2.0)
    body += col
    hx, hy = c["len"] / 2, c["side"]
    # flared on all four sides (45 deg along the belt, 31 across): prints flange-down without a shelf
    body += (prism_xz([(-hx, seat_top), (hx, seat_top), (c["col_x"] / 2, seat_top + flare),
                       (-c["col_x"] / 2, seat_top + flare)], -hy, hy)
             & prism_yz([(-hy, seat_top), (hy, seat_top), (c["col_y"] / 2, seat_top + flare),
                         (-c["col_y"] / 2, seat_top + flare)], -hx, hx))
    body += box(-hx, hx, -hy, hy, z_side, seat_top)
    body -= box(-hx - 1, hx + 1, -c["chan"], c["chan"], z_side - 1, z_ceil)      # belt channel
    for x, y in CLAMP_BOLTS:               # M3 from the plate's top, nuts in pockets under the flange
        body -= cyl_z(P.D_M3 / 2, x, y, z_top - ft - 1, z_top + 1)
        body -= hex_z(NUT3[0] + 0.3, x, y, z_top - ft - 1, z_top - ft + NUT3[1] + 0.3)
    L, r, a = P.LAYER, P.D_M3 / 2, (NUT3[0] + 0.3) / 2
    zn = _jaw_nut_z()
    zf = zn + math.ceil((NUT3[1] + 0.3) / L - 1e-6) * L
    for sx in (-1, 1):                     # jaw screws: up into the side walls, nuts in side slots
        for sy in (-1, 1):
            x, y = sx * c["screw_x"], sy * c["screw_y"]
            y0, y1 = sorted((y - sy * 3.0, sy * (hy + 1)))
            body -= box(x - a, x + a, y0, y1, zn, zf)
            body -= cyl_z(r, x, y, zf - 0.01, z_side + 9.0)
            # the slot's face towards the jaw prints last, as a bridge: the hole starts over it in two
            # one-layer steps, a slot across and then a square, not as walls over the nut's slot
            body -= box(x - a, x + a, y - r, y + r, zn - L, zn + 0.01)
            body -= box(x - r, x + r, y - r, y + r, zn - 2 * L, zn - L + 0.01)
            body -= cyl_z(r, x, y, z_side - 1, zn - 2 * L + 0.01)
    return body


def clamp_jaw():
    """Under the belt: a ridge with HTD tooth seats (one tooth centred at x = 0) that rises into
    the channel, on a base screwed up into the clamp's side walls (4 x M3)."""
    c = P.CLAMP
    _, z_side, z_jaw0 = _clamp_levels()
    hx, hy = c["len"] / 2, c["side"]
    j = box(-hx, hx, -hy, hy, z_jaw0, z_jaw0 + c["jaw_base"])
    j += box(-hx, hx, -c["chan"] + 0.2, c["chan"] - 0.2, z_jaw0 + c["jaw_base"] - 0.01, P.Z_RUN_LAND)
    j -= rack_grooves(-hx - 5, hx + 5, P.Z_RUN_LAND, -c["chan"] - 1, c["chan"] + 1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            j -= cyl_z(P.D_M3 / 2, sx * c["screw_x"], sy * c["screw_y"], z_jaw0 - 1, z_jaw0 + c["jaw_base"] + 1)
    return j


# ================================================================== motor end
def _saddle(x_end_sign, y0, y1):
    """U round the top end bar from below: inner and outer cheeks on its 40 mm faces, web under it."""
    xi = x_end_sign * (P.X_BAR_IN - P.SADDLE_FIT)
    xo = x_end_sign * (P.X_BAR_OUT + P.SADDLE_FIT)
    t = P.SADDLE_T
    zt = P.Z_BAR[1] - 4.0
    s = box(*sorted((xi, xi - x_end_sign * t)), y0, y1, P.SADDLE_WEB[0], zt)
    s += box(*sorted((xo, xo + x_end_sign * t)), y0, y1, P.SADDLE_WEB[0], zt)
    s += box(*sorted((xi - x_end_sign * t, xo + x_end_sign * t)), y0, y1, *P.SADDLE_WEB)
    return s


def _saddle_bolts(s, x_end_sign, bolts):
    t = P.SADDLE_T
    for face, xf, d in (("in", P.X_BAR_IN - P.SADDLE_FIT, -1), ("out", P.X_BAR_OUT + P.SADDLE_FIT, 1)):
        x = x_end_sign * xf
        xa = x + x_end_sign * d * t
        for y, z in bolts[face]:
            s -= cyl_x(P.D_M5 / 2, y, z, *sorted((x - x_end_sign * d, xa + x_end_sign * d)))
            s -= cyl_x(P.HEAD["M5"][0] / 2 + F, y, z, *sorted((xa - x_end_sign * d * 3.0, xa + x_end_sign * d)))
    return s


MOTOR_BOLTS = {face: [(22.0, P.Z_BAR_SLOTS[0]), (40.0, P.Z_BAR_SLOTS[1])] for face in ("in", "out")}
# the idler saddle's inner face is under the web's gusset: all four through the outer face
IDLER_BOLTS = {"in": [], "out": [(y, z) for z in P.Z_BAR_SLOTS for y in (-19.0, 19.0)]}


def motor_mount():
    """Hangs the NEMA 17 under the -x top end bar, shaft along y, pulley on the belt plane (inboard
    of the bar when the belt is short: a web under the bar carries it). Saddle (4 x M5 into T-nuts
    in the bar's 40 mm faces), motor plate with the screw heads sunk so the pulley's flange clears
    them, and side walls either side of the motor body."""
    m = P.NEMA17
    y0, y1 = P.MOTOR_PLATE_Y
    yb = y1 + 32.0
    a = m["side"] / 2
    x0, x1 = P.X_MOTOR - a - 0.8, P.X_MOTOR + a + 0.8
    zb = P.Z_PULLEY - a - 1.0
    s = _saddle(-1, y0, yb)
    s += box(min(x0 - 4.0, -P.X_BAR_OUT), x1 + 4.0, y0, yb, *P.SADDLE_WEB)      # web: saddle to the motor box
    s += box(x0 - 0.01, x1 + 0.01, y0, y1, zb, P.SADDLE_WEB[0] + 0.01)          # motor plate
    for xa, xb in ((x0 - 4.0, x0), (x1, x1 + 4.0)):                            # side walls
        s += box(xa, xb, y0, yb, zb, P.SADDLE_WEB[0] + 0.01)
    s += box(x0 - 4.0, x1 + 4.0, y0, yb, zb - 4.0, zb)                          # floor under the motor
    s -= cyl_y(m["boss"] / 2 + 0.4, P.X_MOTOR, P.Z_PULLEY, y0 - 1, y1 + 1)
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = P.X_MOTOR + sx * m["hole"] / 2, P.Z_PULLEY + sz * m["hole"] / 2
            s -= cyl_y(P.D_M3 / 2, x, z, y0 - 1, y1 + 1)
            s -= cyl_y(P.HEAD["M3"][0] / 2 + F, x, z, y0 - 1, y0 + CB3)
    s -= box(x0 + 6.0, x1 - 6.0, y1 + 6.0, yb + 1, zb - 5.0, zb + 0.01)           # cable slot in the floor
    return _saddle_bolts(s, -1, MOTOR_BOLTS)


def pulley_body(bore="motor"):
    """HTD pulley, local frame (axis z): flange on the bed at z 0..1.5, teeth, boss for the
    pressed-on front flange. Motor: D bore and a sunk M3 set screw with a captive nut."""
    teeth = extrude(pulley_teeth_face(), amount=P.TOOTH_W)
    p = Pos(0, 0, P.FLANGE_T) * teeth
    p += cyl_z(P.R_FLANGE, 0, 0, 0, P.FLANGE_T + 0.01)
    p += cyl_z(6.0, 0, 0, P.FLANGE_T + P.TOOTH_W - 0.01, P.PULLEY_W)
    if bore == "motor":
        d = P.NEMA17["shaft"] + 0.15
        flat = P.NEMA17["shaft"] / 2 - P.NEMA17["flat"] + 0.1      # bore's flat, facing the set screw
        p -= cyl_z(d / 2, 0, 0, -1, P.PULLEY_W + 1)
        p += box(flat, d / 2 + 0.5, -3.0, 3.0, 0, P.PULLEY_W)
        zc = P.FLANGE_T + P.TOOTH_W / 2
        r_root = P.R_TIP - P.GROOVE_DEPTH
        p -= cyl_x(1.7, 0, zc, 0, r_root + 1)                                # set screw, radial along +x
        p -= cyl_x(P.HEAD["M3"][0] / 2 + 0.3, 0, zc, 13.0, r_root + 2)       # its head sunk below the teeth
        p -= box(6.2, 6.2 + NUT3[1] + 0.3, -(NUT3[0] + 0.3) / 2, (NUT3[0] + 0.3) / 2,
                 zc - (NUT3[0] + 0.3) / 2 / math.cos(math.radians(30)), P.PULLEY_W + 1)   # nut drops in from the front
    else:
        p -= cyl_z(4.2, 0, 0, -1, P.PULLEY_W + 1)
    return p


def _pulley_to_assembly(x):
    """Local pulley frame -> assembly: axis along -y, flange on the +y side, centre on (x, Z_PULLEY)."""
    return G.mat4(G.rotation("x", 90.0), (x, P.PULLEY_W / 2, P.Z_PULLEY))


def motor_pulley():
    return pulley_body("motor")


def idler_pulley():
    return pulley_body("idler")


def pulley_flange():
    f = cyl_z(P.R_FLANGE, 0, 0, 0, P.FLANGE_T) - cyl_z(6.0, 0, 0, -1, P.FLANGE_T + 1)
    return f


# ================================================================== idler end
def _window():
    """The slider's window in each cheek. Its lower edge, which the slider rests on, prints last as a
    bridge (the mount prints upside down, the saddle's top on the bed): it has room for that bridge's
    sag and sits on a layer boundary."""
    sl = P.SLIDER
    zc = P.Z_PULLEY - sl["axle_dz"]
    x0, x1 = P.IDLER_TRAVEL[0] - sl["x"] / 2 - F, P.IDLER_TRAVEL[1] + sl["x"] / 2 + F
    z_bed = P.Z_BAR[1] - 4.0
    z0 = zc - sl["z"] / 2 - F - P.BRIDGE_SAG * (x1 - x0)
    return x0, x1, z_bed - math.ceil((z_bed - z0) / P.LAYER - 1e-6) * P.LAYER, zc + sl["z"] / 2 + F


def idler_mount():
    """Saddle on the +x top end bar (4 x M5) with two cheeks either side of the idler. Each cheek
    has a window for an axle slider and, outboard, a lug for its M3 tension screw: the two
    screws pull the axle out to tension the belt and square it so the belt runs centred."""
    y0, y1 = -(P.CHEEK_Y[1] + 7.5), P.CHEEK_Y[1] + 7.5
    s = _saddle(1, y0, y1)
    wx0, wx1, wz0, wz1 = _window()
    cz0 = wz0 - 7.0
    lug = 8.0
    xo = P.X_BAR_OUT + P.SADDLE_FIT + P.SADDLE_T
    xg = P.X_BAR_IN - P.SADDLE_FIT - P.SADDLE_T  # the saddle's inner cheek
    xw = min(wx0 - 7.0, xg)
    s += box(xw, P.X_BAR_IN, y0, y1, *P.SADDLE_WEB)   # web out to the cheeks
    if xg - xw > 0.5:                          # 45 deg gusset over the web's reach: prints upside down unsupported
        zw = P.SADDLE_WEB[1] - 0.01
        s += prism_xz([(xw, zw), (xg + 0.01, zw), (xg + 0.01, zw + xg - xw)], y0, y1)
    for sy in (-1, 1):
        ya, yb = sorted((sy * P.CHEEK_Y[0], sy * P.CHEEK_Y[1]))
        cheek = box(wx0 - 7.0, wx1 + lug, ya, yb, cz0, P.SADDLE_WEB[0] + 0.01)
        cheek -= box(wx0, wx1, ya - 1, yb + 1, wz0, wz1)
        zs = P.Z_PULLEY - P.SLIDER["axle_dz"] + P.SLIDER["screw_dz"]
        cheek -= cyl_x(P.D_M3 / 2, sy * (P.CHEEK_Y[0] + P.CHEEK_T / 2), zs, wx1 - 1, wx1 + lug + 1)
        s += cheek
        if wx1 + lug > xo:                 # cheek reaching past the bar: gusset up the outer saddle cheek
            s += prism_xz([(xo - 0.01, P.SADDLE_WEB[0] - 0.01), (wx1 + lug, P.SADDLE_WEB[0] - 0.01),
                           (xo - 0.01, P.SADDLE_WEB[0] + 24.0)], ya, yb)
    return _saddle_bolts(s, 1, IDLER_BOLTS)


def idler_slider():
    """Slides in the cheek's window (-y cheek, first copy): axle hole, M3 tension screw tapped
    through along x, outer flange that the axle bolt clamps against the cheek to lock it."""
    sl = P.SLIDER
    x = P.X_IDLER
    zc = P.Z_PULLEY - sl["axle_dz"]
    ya, yb = -P.CHEEK_Y[1], -P.CHEEK_Y[0]
    s = box(x - sl["x"] / 2, x + sl["x"] / 2, ya, yb, zc - sl["z"] / 2, zc + sl["z"] / 2)
    s += box(x - sl["x"] / 2 - 4.0, x + sl["x"] / 2 + 4.0, ya - 1.5, ya + 0.01, zc - sl["z"] / 2 - 4.0,
             zc + sl["z"] / 2 + 4.0)
    s -= cyl_y((P.AXLE_D + 0.3) / 2, x, P.Z_PULLEY, ya - 3, yb + 1)
    s -= cyl_x(P.D_M3_TAP / 2, (ya + yb) / 2, zc + sl["screw_dz"], x - sl["x"] / 2 - 5, x + sl["x"] / 2 + 5)
    return s


def idler_sleeve():
    """The idler turns on this sleeve; the axle bolt clamps the sliders against its ends, not
    against the pulley."""
    ya, yb = -P.CHEEK_Y[0], P.CHEEK_Y[0]
    return (cyl_y(P.IDLER_JOURNAL_R, P.X_IDLER, P.Z_PULLEY, ya, yb)
            - cyl_y((P.AXLE_D + 0.4) / 2, P.X_IDLER, P.Z_PULLEY, ya - 1, yb + 1))


# ================================================================== travel ends
def rod_bumper():
    """Split collar on the rod where the cart must stop: against the SK8's inner face, or inboard
    of it when the pulleys sit inboard (first copy: +x end, back rod; its clamp lug points
    outboard in y). The SC8UU stops on it, 4 mm after the limit switch trips."""
    x0, x1 = P.X_BUMPER, P.X_BUMPER + P.BUMPER_W
    y, z = P.Y_ROD, P.Z_ROD
    r = P.BUMPER_OD / 2
    c = cyl_x(r, y, z, x0, x1)
    c += box(x0, x1, y, y + r + 7.0, z - 5.0, z + 5.0)
    c -= cyl_x(P.ROD_D / 2 + 0.15, y, z, x0 - 1, x1 + 1)
    c -= box(x0 - 1, x1 + 1, y, y + r + 8.0, z - 0.75, z + 0.75)           # the split
    xm = (x0 + x1) / 2
    c -= cyl_z(P.D_M3 / 2, xm, y + r + 2.0, z - 6, z + 6)
    c -= hex_z(NUT3[0] + 0.3, xm, y + r + 2.0, z - 6, z - 5.0 + NUT3[1] + 0.3, turn=90)
    return c


def switch_mount():
    """Block on the top end bar (+x first; M5 into a T-nut in the bar's top slot) holding the
    endstop board level with the carriage plate, roller towards the cart."""
    import vitamins as V
    g = V.endstop_geometry(1)
    e = P.ENDSTOP
    x0, x1 = g["x_pcb"][0] + 1.0, g["x_pcb"][1] - 1.0
    y0, y1 = P.Y_SWITCH - 10.0, P.Y_SWITCH + 10.0
    zt = g["z0"]
    blk = box(max(x0, P.X_BAR_IN - 4.0), x1, y0, y1, P.FRAME_H, zt)
    # key in the bar's top slot: square to the bar, cannot turn on its one bolt
    blk += box(P.X_END - (P.SLOT - 0.4) / 2, P.X_END + (P.SLOT - 0.4) / 2, y0, y1, P.FRAME_H - 1.5, P.FRAME_H + 0.01)
    blk -= cyl_z(P.D_M5 / 2, P.X_END, P.Y_SWITCH, P.FRAME_H - 1, zt + 1)
    blk -= cyl_z(P.HEAD["M5"][0] / 2 + 0.6, P.X_END, P.Y_SWITCH, P.FRAME_H + 6.0, zt + 1)
    xc = (g["x_pcb"][0] + g["x_pcb"][1]) / 2
    for sx in (-1, 1):
        xh = xc + sx * e["hole_dx"] / 2
        blk -= slot_z(P.D_M3_TAP / 2, xh - 1.0, P.Y_SWITCH, xh + 1.0, P.Y_SWITCH, zt - 10.0, zt + 1)
    return blk


# ================================================================== pendulum
def _hub_levels():
    z_sock0 = P.Z_SHAFT + 13.0
    return z_sock0, z_sock0 + P.HUB["socket"]


def pendulum_hub():
    """Clamps on the shaft's front end (split below the bore, M3 pinch screw) and holds the arm in
    a socket (2 x M3 through)."""
    y0, y1 = P.Y_HUB
    zs0, zs1 = _hub_levels()
    hw = P.ARM_W / 2 + 3.0
    h = cyl_y(P.HUB["r"], 0, P.Z_SHAFT, y0, y1)
    h += box(-hw, hw, y0, y1, P.Z_SHAFT, zs1)
    # It prints on its back face, the socket on its side: the socket's front face prints last as a
    # bridge, so it gets room for that bridge's sag and sits on a layer boundary, and each arm screw's
    # hole starts over it in two one-layer steps (a slot right across the socket, then a square): each
    # layer bridges between held edges instead of laying the hole's walls over the socket (REPORT R1).
    L, w = P.LAYER, P.ARM_W + 2 * F
    back = P.Y_ARM + P.ARM_T / 2 + F
    front = y1 - math.ceil((y1 - (P.Y_ARM - P.ARM_T / 2 - F) + P.BRIDGE_SAG * w) / L - 1e-6) * L
    h -= box(-w / 2, w / 2, front, back, zs0, zs1 + 1)
    h -= cyl_y((P.SHAFT_D + 0.15) / 2, 0, P.Z_SHAFT, y0 - 1, y1 + 1)
    h -= box(-0.75, 0.75, y0 - 1, y1 + 1, P.Z_SHAFT - P.HUB["r"] - 1, P.Z_SHAFT)
    zc = P.Z_SHAFT - 9.0
    h -= cyl_x(P.D_M3 / 2, (y0 + y1) / 2, zc, -P.HUB["r"] - 1, P.HUB["r"] + 1)
    h -= cyl_x(P.HEAD["M3"][0] / 2 + F, (y0 + y1) / 2, zc, -P.HUB["r"] - 1, -7.0)
    h -= hex_x(NUT3[0] + 0.3, (y0 + y1) / 2, zc, 9.4, P.HUB["r"] + 1)
    r = P.D_M3 / 2
    for z in ARM_SCREWS_Z:                 # heads on the front face, nuts sunk in the back face
        h -= cyl_y(r, 0, z, back - 0.01, y1 + 1)
        h -= box(-w / 2, w / 2, front - L, front + 0.01, z - r, z + r)
        h -= box(-r, r, front - 2 * L, front - L + 0.01, z - r, z + r)
        h -= cyl_y(r, 0, z, y0 - 1, front - 2 * L + 0.01)
        h -= hex_y(NUT3[0] + 0.3, 0, z, y1 - NUT3[1] - 0.3, y1 + 1)
    return h


ARM_SCREWS_Z = (P.Z_SHAFT + 21.0, P.Z_SHAFT + 31.0)


def pendulum_arm():
    """20 x 10 mm bar, the bending plane 20 mm deep; its tip ARM_L from the pivot."""
    zs0, _ = _hub_levels()
    a = box(-P.ARM_W / 2, P.ARM_W / 2, P.Y_ARM - P.ARM_T / 2, P.Y_ARM + P.ARM_T / 2, zs0, P.Z_SHAFT + P.ARM_L)
    for z in ARM_SCREWS_Z:
        a -= cyl_y(P.D_M3 / 2, 0, z, P.Y_ARM - 6, P.Y_ARM + 6)
    a -= cyl_y(P.D_M3 / 2, 0, P.Z_SHAFT + P.ARM_L - 12.0, P.Y_ARM - 6, P.Y_ARM + 6)
    return a


def pendulum_tip():
    """Rounded cap over the arm's tip, pinned with an M3 (a place to add tip mass: washers inside)."""
    t = P.TIP
    zt = P.Z_SHAFT + P.ARM_L
    hx, hy = P.ARM_W / 2 + t["wall"], P.ARM_T / 2 + t["wall"]
    c = box(-hx, hx, P.Y_ARM - hy, P.Y_ARM + hy, zt - t["len"], zt + t["wall"])
    c -= box(-P.ARM_W / 2 - F, P.ARM_W / 2 + F, P.Y_ARM - P.ARM_T / 2 - F, P.Y_ARM + P.ARM_T / 2 + F,
             zt - t["len"] - 1, zt)
    c -= cyl_y(P.D_M3 / 2, 0, zt - 12.0, P.Y_ARM - hy - 1, P.Y_ARM + hy + 1)
    return c


def magnet_cap():
    """On the shaft's back end: holds the AS5600's diametric magnet on the axis, 1.5 mm from the
    chip. M3 set screw (captive nut) onto the shaft."""
    c = P.CAP
    m = P.AS5600
    cap = cyl_y(c["r"], 0, P.Z_SHAFT, c["y0"], c["y1"])
    cap -= cyl_y((P.SHAFT_D + 0.1) / 2, 0, P.Z_SHAFT, c["y0"] - 1, c["y0"] + 8.0)
    cap -= cyl_y(m["magnet_d"] / 2 + 0.1, 0, P.Z_SHAFT, c["y1"] - m["magnet_t"] - 0.1, c["y1"] + 1)
    ym = c["y0"] + 4.0
    cap -= cyl_z(P.D_M3 / 2, 0, ym, P.Z_SHAFT, P.Z_SHAFT + c["r"] + 1)
    cap -= box(-(NUT3[0] + 0.3) / 2, (NUT3[0] + 0.3) / 2, c["y0"] - 1, ym + (NUT3[0] + 0.3) / 2,
               P.Z_SHAFT + 5.0, P.Z_SHAFT + 5.0 + NUT3[1] + 0.3)
    return cap


def coupler():
    """Option for the 600 P/R encoder: flexible beam coupling, 8 mm shaft to the encoder's 6 mm,
    alternating slots so it takes up the misalignment between the KP08s and the encoder's
    bearings. Two M3 set screws, their nuts slid in from the side. Prints on its side, on a flat, so
    the slots stand upright."""
    c = P.COUPLER
    y0, y1 = c["y0"], c["y1"]
    k = cyl_y(c["r"], 0, P.Z_SHAFT, y0, y1)
    k -= box(c["r"] - 2.0, c["r"] + 1.0, y0 - 1, y1 + 1, P.Z_SHAFT - c["r"] - 1, P.Z_SHAFT + c["r"] + 1)
    k -= cyl_y((P.SHAFT_D + 0.1) / 2, 0, P.Z_SHAFT, y0 - 1, y0 + 8.0)
    k -= cyl_y((P.LPD3806["shaft"] + 0.1) / 2, 0, P.Z_SHAFT, y1 - 12.5, y1 + 1)
    for i, ys in enumerate((y0 + 10.0, y0 + 11.6)):
        sz = 1 if i % 2 == 0 else -1
        k -= box(-c["r"] - 1, c["r"] + 1, ys, ys + 0.8, *sorted((P.Z_SHAFT - sz * 2.5, P.Z_SHAFT + sz * (c["r"] + 1))))
    a = NUT3[0] + 0.3
    for ym in (y0 + 4.0, y1 - 6.0):
        k -= cyl_z(P.D_M3 / 2, 0, ym, P.Z_SHAFT, P.Z_SHAFT + c["r"] + 1)
        k -= box(-c["r"] - 1, a / math.sqrt(3), ym - a / 2, ym + a / 2, P.Z_SHAFT + 4.6, P.Z_SHAFT + 4.6 + NUT3[1] + 0.3)
    return k


# ================================================================== cables and electronics
def electronics_tray():
    """Lies on the desk behind the frame, hooked to the back long member (2 x M5 into T-nuts in
    its outer slot). Rows of M3 slots and zip-tie slots for the driver, controller and wiring."""
    t = P.TRAY
    y0 = P.FRAME_W / 2
    tr = prism_xy(_chamfered_rect(-t["x"] / 2, t["x"] / 2, y0 + 2.0, y0 + 2.0 + t["y"], 6.0), 0, t["t"])
    tr += box(-t["x"] / 2, t["x"] / 2, y0 + 0.2, y0 + 5.0, 0, P.EXT - 1.0)
    for row in range(5):
        y = y0 + 22.0 + 20.0 * row
        for sx in (-1, 1):
            tr -= slot_z(1.7, sx * 12.0, y, sx * (t["x"] / 2 - 12.0), y, -1, t["t"] + 1)
    for x in (-t["x"] / 2 + 6.0, t["x"] / 2 - 6.0):
        for y in (y0 + 30.0, y0 + 70.0):
            tr -= box(x - 1.5, x + 1.5, y - 3.0, y + 3.0, -1, t["t"] + 1)
    for sx in (-1, 1):
        tr -= cyl_y(P.D_M5 / 2, sx * 50.0, P.EXT / 2, y0 - 1, y0 + 6.0)
        tr -= cyl_y(P.HEAD["M5"][0] / 2 + F, sx * 50.0, P.EXT / 2, y0 + 2.2, y0 + 6.0)
    return tr


def cable_clip():
    """Bolts into any slot of the frame (M5 + T-nut); a snap-in 7 mm loop for the motor, switch and
    sensor leads. First copy: on the back long member's top face, mid-length."""
    y = P.Y_POST
    z0 = P.EXT
    c = box(-14.0, 14.0, y - 7.0, y + 7.0, z0, z0 + 4.0)
    c -= cyl_z(P.D_M5 / 2, -7.0, y, z0 - 1, z0 + 5)
    ring = cyl_x(7.5, y, z0 + 11.5, 3.0, 11.0) - cyl_x(3.6, y, z0 + 11.5, 2.0, 12.0)
    ring -= box(2.0, 12.0, y - 1.2, y + 1.2, z0 + 14.0, z0 + 20.0)
    return c + ring


# ================================================================== registry
def _rz180_about(x, y):
    return G.mat4(G.rotation("z", 180.0), (2 * x, 2 * y, 0.0))


def _rx180_about(y, z):
    return G.mat4(G.rotation("x", 180.0), (0.0, 2 * y, 2 * z))


def _ry180_about(x, z):
    return G.mat4(G.rotation("y", 180.0), (2 * x, 0.0, 2 * z))


I4 = np.eye(4)
PLA, PETG = "pla", "petg"
# copies: 4x4 matrices taking the first copy to each copy (assembly frame, home pose)
# print: rotations (axis, deg) laying the part on the bed (applied in order)
PARTS = {
    "carriage_plate": dict(fn=carriage_plate, material=PLA, group="cart", copies=[I4], print=[],
                           role="carriage plate on the four SC8UU blocks"),
    "pivot_bridge": dict(fn=pivot_bridge, material=PLA, group="cart", copies=[I4], print=[],
                         role="pivot bridge: both KP08s in line, pendulum in front of the frame, sensor tower"),
    "as5600_mount": dict(fn=as5600_mount, material=PLA, group="cart", copies=[I4], print=[("x", -90)],
                         role="AS5600 adapter on the sensor tower"),
    "belt_clamp": dict(fn=belt_clamp, material=PLA, group="cart", copies=[I4], print=[("x", 180)],
                       role="belt clamp: stiff column from the carriage down to the belt's upper run"),
    "clamp_jaw": dict(fn=clamp_jaw, material=PETG, group="cart", copies=[I4], print=[],
                      role=f"clamp jaw: HTD {P.BELT['pitch']:.0f}M tooth seats under the belt"),
    "motor_mount": dict(fn=motor_mount, material=PETG, group="frame", copies=[I4], print=[("x", 90)],
                        role="motor mount: NEMA 17 under the -x top end bar, pulley on the belt plane"),
    "motor_pulley": dict(fn=motor_pulley, material=PETG, group="motor_pulley", local=True,
                         copies=[_pulley_to_assembly(P.X_MOTOR)], print=[],
                         role=f"HTD {P.BELT['pitch']:.0f}M {P.TEETH}T pulley on the motor shaft (set screw on the flat)"),
    "idler_pulley": dict(fn=idler_pulley, material=PETG, group="idler_pulley", local=True,
                         copies=[_pulley_to_assembly(P.X_IDLER)], print=[],
                         role=f"HTD {P.BELT['pitch']:.0f}M {P.TEETH}T idler on its sleeve"),
    "pulley_flange": dict(fn=pulley_flange, material=PETG, group="pulleys", local=True,
                          copies=[G.mat4(G.rotation("x", 90.0), (P.X_MOTOR, -P.PULLEY_W / 2 + P.FLANGE_T, P.Z_PULLEY)),
                                  G.mat4(G.rotation("x", 90.0), (P.X_IDLER, -P.PULLEY_W / 2 + P.FLANGE_T, P.Z_PULLEY))],
                          print=[], role="front flange, pressed on each pulley's boss"),
    "idler_mount": dict(fn=idler_mount, material=PETG, group="frame", copies=[I4], print=[("x", 180)],
                        role="idler mount: saddle on the +x top end bar, cheeks with slider windows"),
    "idler_slider": dict(fn=idler_slider, material=PETG, group="frame", copies=[I4, _rz180_about(P.X_IDLER, 0.0)],
                         print=[("x", 90)], role="axle slider: tension screw pulls it out, flange locks it"),
    "idler_sleeve": dict(fn=idler_sleeve, material=PETG, group="frame", copies=[I4], print=[("x", 90)],
                         role="sleeve the idler turns on"),
    "rod_bumper": dict(fn=rod_bumper, material=PETG, group="frame",
                       copies=[I4, _rx180_about(0.0, P.Z_ROD), _ry180_about(0.0, P.Z_ROD), _rz180_about(0.0, 0.0)],
                       print=[("y", 90)], role="rod collar: hard stop for the SC8UU blocks"),
    "switch_mount": dict(fn=switch_mount, material=PLA, group="frame", copies=[I4, _rz180_about(0.0, P.Y_SWITCH)],
                         print=[("x", 180)], role="limit-switch block on each top end bar"),
    "pendulum_hub": dict(fn=pendulum_hub, material=PETG, group="pendulum", copies=[I4], print=[("x", -90)],
                         role="pendulum hub: clamps the shaft, holds the arm"),
    "pendulum_arm": dict(fn=pendulum_arm, material=PLA, group="pendulum", copies=[I4], print=[("x", 90)],
                         role=f"pendulum arm, {P.ARM_L:.0f} mm from the pivot to the tip"),
    "pendulum_tip": dict(fn=pendulum_tip, material=PLA, group="pendulum", copies=[I4], print=[("x", 180)],
                         role="tip cap (room for washers as tip mass)"),
    "magnet_cap": dict(fn=magnet_cap, material=PETG, group="pendulum", copies=[I4], print=[("x", 90)],
                       role="magnet cap: AS5600 magnet on the shaft's axis"),
    "coupler": dict(fn=coupler, material=PETG, group="pendulum_opt", copies=[I4], print=[("y", 90)],
                    role="option: flexible coupling to a 600 P/R optical encoder (instead of the magnet cap)"),
    "electronics_tray": dict(fn=electronics_tray, material=PLA, group="frame", copies=[I4], print=[],
                             role="electronics tray behind the frame"),
    "cable_clip": dict(fn=cable_clip, material=PETG, group="frame",
                       copies=[I4, G.mat4(None, (150.0, 0.0, 0.0)), G.mat4(None, (-150.0, 0.0, 0.0))],
                       print=[], role="cable clip for any slot of the frame"),
}


def build(names=None, write=True, verbose=True):
    """Build the parts; write parts/assembly/<name>.stl (first copy in its own frame: assembly
    frame, or the pulley frame for `local` parts). Returns {name: solid}."""
    out = {}
    os.makedirs(G.ASSEMBLY, exist_ok=True)
    for name in names or PARTS:
        part = PARTS[name]["fn"]()
        if not part.is_valid:
            raise RuntimeError(f"{name}: invalid solid")
        out[name] = part
        if write:
            export(part, os.path.join(G.ASSEMBLY, name + ".stl"))
        if verbose:
            bb = part.bounding_box()
            print(f"{name:18s} {PARTS[name]['material']:4s} x{len(PARTS[name]['copies'])}  vol {part.volume / 1000:7.1f} cm3  "
                  f"x {bb.min.X:7.1f}..{bb.max.X:7.1f}  y {bb.min.Y:7.1f}..{bb.max.Y:7.1f}  z {bb.min.Z:6.1f}..{bb.max.Z:6.1f}",
                  flush=True)
    return out


if __name__ == "__main__":
    build(sys.argv[1:] or None)

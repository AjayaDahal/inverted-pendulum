"""Every screw, nut and T-nut, with where it goes (head position p0, unit vector u into the work)
and what it clamps (stack, mm), so the gate can check each length and the viewer can draw it.
All from the owner's stock: M3, M4 (the SC8UU screws) and M5 with 20-series T-nuts."""
import numpy as np

import params as P
import structure as S

HOLE_M3_FLAT = 4.5      # thread depth in a NEMA 17


def _b(name, size, length, p0, u, group, part, stack, nut=False, tnut=False, into=None, note=""):
    """stack: material between the head and the nut / the start of the thread it screws into."""
    return dict(name=name, size=size, length=float(length), p0=[float(v) for v in p0], u=[float(v) for v in u],
                group=group, part=part, stack=float(stack), nut=nut, tnut=tnut, into=into, note=note)


def _copies(bolts, mats):
    out = []
    for k, M in enumerate(mats):
        M = np.asarray(M, float)
        for b in bolts:
            c = dict(b)
            c["name"] = f"{b['name']}_{k + 1}" if len(mats) > 1 else b["name"]
            c["p0"] = [float(v) for v in M[:3, :3] @ np.array(b["p0"]) + M[:3, 3]]
            c["u"] = [float(v) for v in M[:3, :3] @ np.array(b["u"])]
            out.append(c)
    return out


def bolts():
    out = []
    cb4 = P.Z_PLATE1 - S.CB4
    for i, (x, y) in enumerate(S.SC_HOLES):
        out.append(_b(f"sc8uu_screw_{i + 1}", "M4", 10, (x, y, cb4), (0, 0, -1), "cart", "carriage_plate",
                      P.PLATE_T - S.CB4, into="SC8UU", note="M4 x 10 into the SC8UU's thread (the old plate's screws)"))
    for i, (x, y) in enumerate(S.BRIDGE_BOLTS):
        out.append(_b(f"bridge_bolt_{i + 1}", "M5", 20, (x, y, P.Z_PLATE1 + 6.0), (0, 0, -1), "cart", "pivot_bridge",
                      6.0 + P.PLATE_T, nut=True, note="M5 x 20 + washer, nut in the plate's pocket"))
    for i, (x, y) in enumerate(S.CLAMP_BOLTS):
        out.append(_b(f"clamp_bolt_{i + 1}", "M3", 16, (x, y, P.Z_PLATE1 - S.CB3), (0, 0, -1), "cart", "belt_clamp",
                      P.PLATE_T - S.CB3 + P.CLAMP["flange"][2], nut=True, note="M3 x 16, nut under the clamp's flange"))
    for y in (P.Y_KP_F, P.Y_KP_R):
        for sx in (-1, 1):
            out.append(_b(f"kp08_bolt_{'fr'[y == P.Y_KP_R]}{'lr'[sx > 0]}", "M5", 16,
                          (sx * P.KP08["j"] / 2, y, P.Z_BRIDGE1 + P.KP08["base_t"]), (0, 0, -1), "cart", "pivot_bridge",
                          P.KP08["base_t"] + P.BRIDGE_T - 6.0, nut=True, note="M5 x 16, nut in the bridge's pocket"))
    _, z_side, z_jaw0 = S._clamp_levels()
    for sx in (-1, 1):
        for sy in (-1, 1):
            out.append(_b(f"jaw_screw_{'lr'[sx > 0]}{'fb'[sy > 0]}", "M3", 12,
                          (sx * P.CLAMP["screw_x"], sy * P.CLAMP["screw_y"], z_jaw0), (0, 0, 1), "cart", "clamp_jaw",
                          P.CLAMP["jaw_base"] + 0.6 + 3.8, nut=True, note="M3 x 12, nut in the clamp's side slot"))
    for sx in (-1, 1):
        for sz in (-1, 1):
            out.append(_b(f"motor_screw_{'lr'[sx > 0]}{'bt'[sz > 0]}", "M3", 8,
                          (P.X_MOTOR + sx * P.NEMA17["hole"] / 2, P.MOTOR_PLATE_Y[0] + S.CB3, P.Z_PULLEY + sz * P.NEMA17["hole"] / 2),
                          (0, 1, 0), "frame", "motor_mount", P.MOTOR_PLATE_Y[1] - P.MOTOR_PLATE_Y[0] - S.CB3, into="NEMA 17",
                          note="M3 x 8 (the motor's own screws), heads sunk under the pulley's flange"))
    t = P.SADDLE_T
    for end, sgn, yz in (("motor", -1, S.MOTOR_BOLTS_YZ), ("idler", 1, S.IDLER_BOLTS_YZ)):
        for face, xf, d in (("in", P.X_BAR_IN, -1), ("out", P.X_BAR_OUT, 1)):
            xa = sgn * xf + sgn * d * t
            for j, (y, z) in enumerate(yz):
                out.append(_b(f"{end}_saddle_{face}_{j + 1}", "M5", 10, (xa - sgn * d * 3.0, y, z), (-sgn * d, 0, 0), "frame",
                              f"{end}_mount", t - 3.0, tnut=True, note="M5 x 10 into a T-nut in the top end bar's slot"))
    zc = P.FLANGE_T + P.TOOTH_W / 2
    out.append(_b("set_screw", "M3", 12, (P.X_MOTOR + 13.0, P.PULLEY_W / 2 - zc, P.Z_PULLEY), (-1, 0, 0), "motor_pulley",
                  "motor_pulley", 13.0 - 8.7 - 2.5, nut=True, note="M3 x 12 set screw, head sunk below the teeth, captive nut"))
    ya = -(P.CHEEK_Y[1] + 1.5)
    out.append(_b("idler_axle", "M5", 40, (P.X_IDLER, ya, P.Z_PULLEY), (0, 1, 0), "frame", "idler_slider",
                  2 * (P.CHEEK_T + 1.5) + 2 * P.CHEEK_Y[0], nut=True, note="M5 x 40 axle + nut: clamps sliders and sleeve"))
    wx1 = S._window()[1]
    zs = P.Z_PULLEY - P.SLIDER["axle_dz"] + P.SLIDER["screw_dz"]
    for sy in (-1, 1):
        y = sy * (P.CHEEK_Y[0] + P.CHEEK_T / 2)
        out.append(_b(f"tension_screw_{'fb'[sy > 0]}", "M3", 30, (wx1 + 8.0, y, zs), (-1, 0, 0), "frame", "idler_mount",
                      8.0 + (wx1 - P.X_IDLER - P.SLIDER["x"] / 2), into="slider",
                      note="M3 x 30 through the lug into the slider (tapped)"))
    out += _copies([_b("bumper_screw", "M3", 12, ((2 * P.X_SK8_IN - P.BUMPER_W) / 2, P.Y_ROD + P.BUMPER_OD / 2 + 2.0,
                                                   P.Z_ROD + 5.0), (0, 0, -1), "frame", "rod_bumper", 10.0 - 1.0, nut=True,
                       note="M3 x 12 + nut: clamps the collar")], S.PARTS["rod_bumper"]["copies"])
    import vitamins as V
    g = V.endstop_geometry(1)
    xc = (g["x_pcb"][0] + g["x_pcb"][1]) / 2
    sw = [_b("switch_bolt", "M5", 12, (P.X_END, P.Y_SWITCH, P.FRAME_H + 6.0), (0, 0, -1), "frame", "switch_mount", 6.0,
             tnut=True, note="M5 x 12 into a T-nut in the bar's top slot")]
    for sx in (-1, 1):
        sw.append(_b(f"endstop_screw_{'lr'[sx > 0]}", "M3", 8, (xc + sx * P.ENDSTOP["hole_dx"] / 2, P.Y_SWITCH,
                                                                g["z0"] + P.ENDSTOP["pcb"][2]), (0, 0, -1), "frame",
                     "switch_mount", P.ENDSTOP["pcb"][2], into="switch_mount", note="M3 x 8 self-tapped into the block"))
    out += _copies(sw, S.PARTS["switch_mount"]["copies"])
    y0, y1 = P.Y_HUB
    out.append(_b("hub_pinch", "M3", 20, (-7.0, (y0 + y1) / 2, P.Z_SHAFT - 9.0), (1, 0, 0), "pendulum", "pendulum_hub",
                  16.4, nut=True, note="M3 x 20 + nut: clamps the hub on the shaft"))
    for i, z in enumerate(S.ARM_SCREWS_Z):
        out.append(_b(f"arm_screw_{i + 1}", "M3", 20, (0, y0, z), (0, 1, 0), "pendulum", "pendulum_hub",
                      P.HUB["len"] - P.NUT["M3"][1] - 0.3, nut=True, note="M3 x 20 + nut through the hub and the arm"))
    hy = P.ARM_T / 2 + P.TIP["wall"]
    out.append(_b("tip_pin", "M3", 20, (0, P.Y_ARM - hy, P.Z_SHAFT + P.ARM_L - 12.0), (0, 1, 0), "pendulum", "pendulum_tip",
                  2 * hy, nut=True, note="M3 x 20 + nut: pins the tip cap"))
    out.append(_b("cap_set_screw", "M3", 8, (0, P.CAP["y0"] + 4.0, P.Z_SHAFT + P.CAP["r"]), (0, 0, -1), "pendulum",
                  "magnet_cap", P.CAP["r"] - 5.0 - P.NUT["M3"][1], nut=True, note="M3 x 8 set screw onto the shaft"))
    for i, (x, z) in enumerate(S.AS_MOUNT_HOLES):
        out.append(_b(f"as5600_mount_{i + 1}", "M3", 12, (x, P.Y_TOWER - 3.0, z), (0, 1, 0), "cart", "as5600_mount",
                      3.0 + P.TOWER_T - P.NUT["M3"][1] - 0.3, nut=True, note="M3 x 12, nut in the tower's back"))
    for sx in (-1, 1):
        out.append(_b(f"tray_bolt_{'lr'[sx > 0]}", "M5", 10, (sx * 50.0, P.FRAME_W / 2 + 2.2, P.EXT / 2), (0, -1, 0),
                      "frame", "electronics_tray", 2.2 - 0.2, tnut=True, note="M5 x 10 into a T-nut in the long member"))
    out += _copies([_b("clip_bolt", "M5", 10, (-7.0, P.Y_POST, P.EXT + 4.0), (0, 0, -1), "frame", "cable_clip", 4.0,
                       tnut=True, note="M5 x 10 into a T-nut")], S.PARTS["cable_clip"]["copies"])
    return out


def counts(bolt_list=None):
    """{'M3 x 12': n, ..., 'M3 nut': n, 'T-nut M5': n}"""
    c = {}
    for b in bolt_list or bolts():
        k = f"{b['size']} x {b['length']:.0f}"
        c[k] = c.get(k, 0) + 1
        if b["nut"]:
            c[f"{b['size']} nut"] = c.get(f"{b['size']} nut", 0) + 1
        if b["tnut"]:
            c["T-nut M5 (20-series)"] = c.get("T-nut M5 (20-series)", 0) + 1
    return dict(sorted(c.items()))


if __name__ == "__main__":
    bl = bolts()
    for k, v in counts(bl).items():
        print(f"{k:24s} {v}")
    print(len(bl), "fasteners")

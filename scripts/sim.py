"""Cart-pole model of this machine, from its own geometry and masses: an LQR balance controller
and an energy swing-up, simulated against the stepper's force and speed limits, the AS5600's
12-bit angle and the cart's travel. It answers "can this machine swing the pendulum up and hold
it, within the rails?" and gives the firmware its starting gains.

The control input is the cart's acceleration (a stepper sets motion, not force); the motor force
it takes is computed and checked against the torque available at speed.

Writes parts/sim.json (numbers, gains, a 30 fps trajectory for the viewer) and
renders/52_sim_swingup.png. check_parts.py re-runs it.
"""
import json
import math
import os
import sys

import numpy as np

import assembly as A
import geom as G
import hardware as H
import params as P
import structure as S

FILL = 0.55          # printed parts' mass as a fraction of solid, until the G-code gives it
CTRL_HZ, SIM_HZ = 200, 2000
ANGLE_BITS = 12      # AS5600


def printed_grams(name):
    """Sliced mass (G-code) if the part has been sliced, else volume x density x FILL."""
    try:
        import slice_all
        g = slice_all.part_grams(name)
        if g:
            return g, "sliced"
    except Exception:
        pass
    tris = G.read_stl(os.path.join(G.ASSEMBLY, name + ".stl"))
    vol = abs(G.signed_volume(tris)) / 1000.0
    return vol * P.DENSITY[S.PARTS[name]["material"]] * FILL, "estimate"


def bolt_grams(b):
    d = float(b["size"][1:])
    head = math.pi / 4 * (1.65 * d) ** 2 * d
    g = (math.pi / 4 * d * d * b["length"] + head) * P.STEEL / 1000.0
    if b["nut"]:
        g += 0.25 * d * d * d * P.STEEL / 1000.0 * 1.2
    return g


def mass_model():
    """Masses (kg), the pendulum's CG distance and inertia about the pivot, and the cart's
    effective mass (belt and spinning parts reflected to the cart)."""
    zc = P.Z_SHAFT
    pend = dict(m=0.0, mz=0.0, J=0.0, parts={})
    for name in ("pendulum_hub", "pendulum_arm", "pendulum_tip", "magnet_cap"):
        grams, how = printed_grams(name)
        tris = G.read_stl(os.path.join(G.ASSEMBLY, name + ".stl"))
        vol, cen, m2 = A.mesh_props(tris)
        rho = grams / 1000.0 / vol                                     # kg/mm^3, effective
        J = rho * (m2["xx"] + m2["zz"] - 2 * zc * cen[2] * vol + zc * zc * vol) * 1e-6
        pend["m"] += grams / 1000.0
        pend["mz"] += grams / 1000.0 * (cen[2] - zc) / 1000.0
        pend["J"] += J
        pend["parts"][name] = dict(g=round(grams, 1), how=how)
    for name, dens in (("pivot_shaft", P.STEEL), ("magnet", 7.5)):
        tris = G.read_stl(os.path.join(G.VITAMINS, name + ".stl"))
        vol, cen, m2 = A.mesh_props(tris)
        m = vol * dens / 1e6
        pend["m"] += m
        pend["mz"] += m * (cen[2] - zc) / 1000.0
        pend["J"] += dens / 1e6 * (m2["xx"] + m2["zz"] - 2 * zc * cen[2] * vol + zc * zc * vol) * 1e-6
        pend["parts"][name] = dict(g=round(m * 1000, 1), how="steel" if name == "pivot_shaft" else "magnet")
    cart = dict(m=0.0, parts={})
    for b in H.bolts():
        g = bolt_grams(b) / 1000.0
        if b["group"] == "pendulum":
            p = np.array(b["p0"]) + np.array(b["u"]) * b["length"] / 2
            r2 = ((p[0]) ** 2 + (p[2] - zc) ** 2) * 1e-6
            pend["m"] += g
            pend["mz"] += g * (p[2] - zc) / 1000.0
            pend["J"] += g * r2
        elif b["group"] == "cart":
            cart["m"] += g
    cart["parts"]["screws"] = round(cart["m"] * 1000, 1)
    for name in ("carriage_plate", "pivot_bridge", "as5600_mount", "belt_clamp", "clamp_jaw"):
        grams, how = printed_grams(name)
        cart["m"] += grams / 1000.0
        cart["parts"][name] = dict(g=round(grams, 1), how=how)
    for k, kg in P.MASS_VITAMINS_CART.items():
        cart["m"] += kg
        cart["parts"][k] = round(kg * 1000, 1)
    r = P.PD / 2 / 1000.0
    belt = P.BELT["kg_per_m"] * P.BELT_LOOP / 1000.0
    pulley_kg = printed_grams("motor_pulley")[0] / 1000.0
    j_spin = P.NEMA17["rotor"] + 2 * 0.5 * pulley_kg * (P.R_TIP / 1000.0) ** 2
    m_eff = cart["m"] + belt + j_spin / r ** 2
    l = pend["mz"] / pend["m"]
    f_max = P.MOTOR_TORQUE_USE * P.NEMA17["torque"] / r
    return dict(m_cart=cart["m"], m_belt=belt, m_spin=j_spin / r ** 2, m_eff=m_eff, m_p=pend["m"], l=l, J=pend["J"],
                r=r, f_max=f_max, a_max=0.8 * f_max / (m_eff + pend["m"]), v_max=P.V_MAX, x_soft=P.X_SOFT / 1000.0,
                pend_parts=pend["parts"], cart_parts=cart["parts"])


def lqr(m, q=(60.0, 4.0, 40.0, 1.0), r=0.6):
    """Continuous LQR on the upright linearisation, input = cart acceleration."""
    a = m["m_p"] * P.G_ACC * m["l"] / m["J"]
    b = m["m_p"] * m["l"] / m["J"]
    A_ = np.array([[0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 1], [0, 0, a, 0]], float)
    B_ = np.array([[0], [1], [0], [-b]], float)
    Q = np.diag(q)
    R = np.array([[r]])
    Hm = np.block([[A_, -B_ @ np.linalg.inv(R) @ B_.T], [-Q, -A_.T]])
    w, vecs = np.linalg.eig(Hm)
    st = vecs[:, w.real < 0]
    X = np.real(st[4:] @ np.linalg.inv(st[:4]))
    K = (np.linalg.inv(R) @ B_.T @ X).ravel()
    poles = np.linalg.eigvals(A_ - B_ @ K[None, :])
    return K, poles, a, b


def simulate(m, K, t_end=14.0, theta0=math.pi - 0.05, kick_at=10.0, kick=1.0, swing=(3.0, 2.5, 1.6),
             catch=(25.0, 5.0), e_ref=0.0, ctrl=None):
    """Start hanging, swing up, catch with the LQR, take a kick (rad/s) at kick_at. swing: (pump
    acceleration, cart centring gains kx, kv); catch: (window deg, max rad/s); e_ref: energy the
    swing-up aims at, as a fraction of m g l above upright rest. `m` is the plant; `ctrl` the
    model the controller believes (default: the plant)."""
    a_s, kx, kv = swing
    g, l, J, mp = P.G_ACC, m["l"], m["J"], m["m_p"]
    c = ctrl or m
    cl, cJ, cmp = c["l"], c["J"], c["m_p"]
    s = np.array([0.0, 0.0, theta0, 0.0])
    n_sub = SIM_HZ // CTRL_HZ
    dt = 1.0 / SIM_HZ
    q = 2 * math.pi / 2 ** ANGLE_BITS
    th_prev = None
    w_est = 0.0
    mode, u = "swing", 0.0
    log = []
    t_catch = None
    for k in range(int(t_end * CTRL_HZ)):
        t = k / CTRL_HZ
        if kick_at is not None and abs(t - kick_at) < 0.5 / CTRL_HZ:
            s[3] += kick
        th_m = round(s[2] / q) * q
        th_w = (th_m + math.pi) % (2 * math.pi) - math.pi
        if th_prev is None:
            th_prev = th_m
        w_raw = (th_m - th_prev) * CTRL_HZ
        th_prev = th_m
        w_est += (w_raw - w_est) * 0.35
        E = 0.5 * cJ * w_est ** 2 + cmp * g * cl * (math.cos(th_w) - 1.0) - e_ref * cmp * g * cl
        if mode == "swing" and math.cos(th_w) > math.cos(math.radians(catch[0])) and abs(w_est) < catch[1]:
            mode = "lqr"
            t_catch = t_catch or t
        elif mode == "lqr" and abs(th_w) > math.radians(45):
            mode = "swing"
        if mode == "lqr":
            u = -float(K @ np.array([s[0], s[1], th_w, w_est]))
        else:
            # energy pumping (Astrom-Furuta, softened with tanh: no lurch at the start, no chatter
            # near the target) plus a cart-centring spring and damper
            w0 = math.sqrt(cmp * g * cl / cJ)
            pump = -a_s * math.tanh(3.0 * (-E) / (cmp * g * cl)) * math.tanh(2.0 * w_est * math.cos(th_w) / w0)
            u = pump - kx * s[0] - kv * s[1]
        u = max(-c["a_max"], min(c["a_max"], u))
        for _ in range(n_sub):
            uu = max(-m["a_max"], min(m["a_max"], u))          # what the plant's motor can give
            if (s[1] >= m["v_max"] and uu > 0) or (s[1] <= -m["v_max"] and uu < 0):
                uu = 0.0

            def f(st):
                th, w = st[2], st[3]
                wd = (mp * g * l * math.sin(th) - mp * l * uu * math.cos(th) - 2e-4 * w) / J
                return np.array([st[1], uu, w, wd])
            k1 = f(s)
            k2 = f(s + dt / 2 * k1)
            k3 = f(s + dt / 2 * k2)
            k4 = f(s + dt * k3)
            s = s + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        th, w = s[2], s[3]
        wd = (mp * g * l * math.sin(th) - mp * l * u * math.cos(th)) / J
        xcg_dd = u + l * (wd * math.cos(th) - w * w * math.sin(th))
        F = m["m_eff"] * u + mp * xcg_dd + 1.0 * math.copysign(1.0, s[1]) * (abs(s[1]) > 1e-4)
        log.append((t, s[0], s[1], (s[2] + math.pi) % (2 * math.pi) - math.pi, u, F, mode == "lqr"))
    return np.array(log, float), t_catch


LQR_SETS = {"soft": ((60, 4, 40, 1), 0.6), "mid": ((300, 30, 40, 1), 1.0), "firm": ((1000, 80, 60, 2), 2.0),
            "stiff": ((3000, 200, 100, 3), 5.0)}
# Candidates from a random search (DESIGN.md, "Control"): LQR set, swing (pump, kx, kv), catch
# (deg, rad/s), energy target. run() keeps the one with the best worst case over PLANTS.
CANDIDATES = [("stiff", (1.74, 11.0, 1.12), (10.1, 4.9), 0.108), ("firm", (3.31, 8.1, 4.78), (13.0, 4.8), 0.089),
              ("stiff", (3.15, 2.7, 3.93), (15.0, 4.6), 0.197), ("stiff", (3.6, 8.15, 5.61), (21.8, 3.6), 0.083),
              ("firm", (2.59, 2.68, 1.92), (11.2, 4.0), 0.172), ("mid", (2.11, 9.15, 1.31), (16.8, 4.8), 0.17),
              ("mid", (2.82, 1.35, 1.27), (22.1, 1.9), 0.155), ("stiff", (2.92, 4.12, 2.43), (19.0, 3.6), 0.072),
              ("mid", (3.38, 8.52, 4.36), (11.5, 3.5), 0.18)]
# The real machine will differ from the model: pendulum mass and inertia +-20 %, CG +-15 %,
# cart mass +-20 %. Each candidate must swing up and hold on all of these.
PLANTS = [dict(), dict(m_p=0.8, J=0.8), dict(m_p=1.2, J=1.2), dict(l=0.85, J=0.85), dict(l=1.15, J=1.15),
          dict(m_eff=1.2, a_max=1 / 1.2)]


def _plant(m, scale):
    p = dict(m)
    for k, f in scale.items():
        p[k] = p[k] * f
    return p


def evaluate(m, cand, t_end=13.0, kick_at=10.0):
    lq, swing, catch, e_ref = cand
    K = lqr(m, *LQR_SETS[lq])[0]
    worst = dict(x=0.0, f=0.0, v=0.0, t=0.0, ok=True)
    nominal = None
    for scale in PLANTS:
        log, tc = simulate(_plant(m, scale), K, t_end=t_end, swing=swing, catch=catch, e_ref=e_ref, kick=1.0,
                           kick_at=kick_at, ctrl=m)
        ok = tc is not None and tc < kick_at - 1.0 and bool(log[-200:, 6].all())
        worst["ok"] &= ok
        worst["x"] = max(worst["x"], float(np.abs(log[:, 1]).max()))
        worst["f"] = max(worst["f"], float(np.abs(log[:, 5]).max()))
        worst["v"] = max(worst["v"], float(np.abs(log[:, 2]).max()))
        worst["t"] = max(worst["t"], tc if tc is not None else 99.0)
        if not scale:
            nominal = (log, tc)
    return worst, nominal, K


def run(write=True, verbose=True):
    m = mass_model()
    best = None
    for cand in CANDIDATES:
        worst, nominal, K = evaluate(m, cand)
        key = (not worst["ok"], worst["x"] > m["x_soft"], worst["x"])
        if best is None or key < best[0]:
            best = (key, cand, worst, nominal, K)
    _, cand, worst, (log, t_catch), K = best
    poles = lqr(m, *LQR_SETS[cand[0]])[1]
    a = m["m_p"] * P.G_ACC * m["l"] / m["J"]
    after = log[(log[:, 0] > (t_catch or 0) + 1.5) & (log[:, 0] < 10.0)]
    res = dict(
        masses=dict(cart_kg=round(m["m_cart"], 3), belt_kg=round(m["m_belt"], 3), spinning_kg=round(m["m_spin"], 3),
                    effective_kg=round(m["m_eff"], 3), pendulum_kg=round(m["m_p"], 4), cg_m=round(m["l"], 4),
                    J_kgm2=round(m["J"], 6), cart_parts=m["cart_parts"], pendulum_parts=m["pend_parts"]),
        limits=dict(f_max_N=round(m["f_max"], 2), a_max=round(m["a_max"], 2), v_max=m["v_max"], x_soft_m=m["x_soft"]),
        natural_rad_s=round(math.sqrt(a), 3), lqr_set=cand[0], lqr_Q=list(LQR_SETS[cand[0]][0]), lqr_R=LQR_SETS[cand[0]][1],
        lqr_K=[round(float(k), 3) for k in K],
        lqr_poles=[[round(float(p.real), 3), round(float(p.imag), 3)] for p in poles],
        swing=dict(pump=cand[1][0], kx=cand[1][1], kv=cand[1][2], catch_deg=cand[2][0], catch_rad_s=cand[2][1],
                   e_ref=cand[3]),
        swing_up_s=None if t_catch is None else round(t_catch, 2),
        x_max_m=round(float(np.abs(log[:, 1]).max()), 4), v_max_m_s=round(float(np.abs(log[:, 2]).max()), 3),
        f_peak_N=round(float(np.abs(log[:, 5]).max()), 2), balanced_at_end=bool(log[-200:, 6].all()),
        theta_rms_balanced_deg=round(float(np.degrees(np.sqrt(np.mean(after[:, 3] ** 2)))), 3) if len(after) else None,
        robust=dict(plants=len(PLANTS), all_ok=worst["ok"], x_max_m=round(worst["x"], 4), f_peak_N=round(worst["f"], 2),
                    v_max_m_s=round(worst["v"], 3), swing_up_s=round(worst["t"], 2)),
        kick_rad_s=1.0, steps_per_mm=round(P.STEPS_PER_REV / (math.pi * P.PD), 3), mm_per_rev=round(math.pi * P.PD, 3),
    )
    dec = max(1, CTRL_HZ // 30)
    res["trajectory"] = dict(fps=CTRL_HZ / dec, t=[round(float(v), 3) for v in log[::dec, 0]],
                             x_mm=[round(float(v) * 1000, 2) for v in log[::dec, 1]],
                             theta_deg=[round(float(math.degrees(v)), 2) for v in log[::dec, 3]],
                             mode=[int(v) for v in log[::dec, 6]])
    if write:
        with open(os.path.join(G.PARTS_DIR, "sim.json"), "w", newline="\n") as f:
            json.dump(res, f, indent=1)
        plot(log, res)
    if verbose:
        print(json.dumps({k: v for k, v in res.items() if k not in ("trajectory", "masses")}, indent=1))
    return res


def plot(log, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = log[:, 0]
    fig, ax = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True)
    ax[0].plot(t, np.degrees(log[:, 3]), color="#2f6db5")
    ax[0].set_ylabel("pendulum (deg, 0 = up)")
    ax[0].axhline(0, color="#888", lw=0.6)
    ax[1].plot(t, log[:, 1] * 1000, color="#e2873a", label="cart position")
    for s in (-1, 1):
        ax[1].axhline(s * P.X_SOFT, color="#c0392b", lw=0.8, ls="--")
        ax[1].axhline(s * P.X_STOP, color="#c0392b", lw=1.2)
    ax[1].set_ylabel("cart (mm)")
    ax[2].plot(t, log[:, 5], color="#555", label="motor force needed")
    for s in (-1, 1):
        ax[2].axhline(s * res["limits"]["f_max_N"], color="#c0392b", lw=0.8, ls="--")
    ax[2].set_ylabel("force (N)")
    ax[2].set_xlabel("time (s)")
    lq = log[:, 6] > 0.5
    for a in ax:
        a.fill_between(t, 0, 1, where=lq, transform=a.get_xaxis_transform(), color="#2ea44f", alpha=0.08)
        a.grid(alpha=0.25)
    fig.suptitle(f"Swing-up from hanging, caught at {res['swing_up_s']} s, kicked at 10 s (green: balancing)")
    fig.tight_layout()
    os.makedirs(os.path.join(G.ROOT, "renders"), exist_ok=True)
    fig.savefig(os.path.join(G.ROOT, "renders", "52_sim_swingup.png"), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    run(write="--no-write" not in sys.argv)

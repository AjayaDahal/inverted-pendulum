"""Cart-pole model of this machine, from its own geometry and masses, and the controller the
firmware runs: `Controller` here and firmware/pendulum/controller.h are the same code, line for
line (check_parts.py replays a simulation through the C++). From hanging still it kicks the
pendulum, pumps energy in, catches it near the top and balances it with an LQR that has integral
action on the cart's position.

The model includes what the premortem (REPORT.md) found can make the real machine fail:
- the stepper's force at speed (torque-speed curve at the driver's current and supply), against
  what the motion needs plus the friction at the cart (rails, belt, the idler's plain journal);
- a delay from reading the angle to the motor moving (the step generator plans ahead);
- Coulomb friction at the pivot: two sealed KP08s let the pendulum rest a few degrees off
  vertical, so the swing-up has to start it; balanced, the same friction makes the pendulum hunt
  (stick-slip) by an amount the gains hardly change: `hunting` gives it against the friction, and
  the nominal run uses the pivot's goal (params.PIVOT_FRICTION_GOAL);
- an error in the upright calibration, and the sensor's resolution (AS5600 or 600 P/R encoder).
The controller must swing up, hold and take a push on every ROBUST run, inside the soft limits
and the force budget.

Writes parts/sim.json and renders/52_sim_swingup.png. check_parts.py re-runs it;
tune_controller.py searches for CANDIDATES.
"""
import json
import math
import os
import sys
from collections import deque

import numpy as np

import geom as G
import params as P

FILL = 0.55          # printed parts' mass as a fraction of solid, until the G-code gives it
CTRL_HZ, SIM_HZ = P.CTRL_HZ, 1000
T_END, PUSH_AT, PUSH = 15.0, 12.0, 0.7     # s; a 0.7 rad/s push once it balances
X_MARGIN = 0.015                           # m every run keeps from the soft limit
# The real machine differs from the model: pendulum mass and inertia +-20 %, CG +-15 %, cart +20 %
PLANTS = [dict(), dict(m_p=0.8, J=0.8), dict(m_p=1.2, J=1.2), dict(l=0.85, J=0.85), dict(l=1.15, J=1.15),
          dict(m_eff=1.2)]
# ...on each corner: delay (s), pivot friction (N m), upright error (deg), sensor counts per turn
# (AS5600 4096, 600 P/R encoder 2400). The hardest first: tune_controller.py stops at a failure.
CORNERS = [dict(delay=P.ACT_DELAY[1], tau=P.PIVOT_FRICTION, offset=-P.ANGLE_OFFSET, counts=2400),
           dict(delay=P.ACT_DELAY[1], tau=0.0, offset=P.ANGLE_OFFSET, counts=4096),
           dict(delay=P.ACT_DELAY[0], tau=P.PIVOT_FRICTION, offset=P.ANGLE_OFFSET, counts=2400),
           dict(delay=P.ACT_DELAY[0], tau=0.0, offset=-P.ANGLE_OFFSET, counts=4096)]
NOMINAL = dict(delay=sum(P.ACT_DELAY) / 2, tau=P.PIVOT_FRICTION_GOAL, offset=0.0, counts=4096)
# Balanced, peak-to-peak hunting against pivot friction (N m); the most allowed at the goal
HUNT_TAUS = sorted({0.0, 0.00025, P.PIVOT_FRICTION_GOAL, 0.001, 0.0015, 0.002, P.PIVOT_FRICTION})
HUNT_LIMIT = dict(theta_pp_deg=2.0, cart_pp_mm=25.0)


def _robust_runs():
    """(plant scale, scenario, push, start angle) of every run: PLANTS x CORNERS with the push
    alternating in direction, then 24 random runs inside the same bounds (fixed seed): the model
    errors together, conditions between the corners, the pendulum resting off vertical."""
    import random
    runs = [(scale, sc, PUSH if (i + j) % 2 == 0 else -PUSH, math.pi)
            for j, sc in enumerate(CORNERS) for i, scale in enumerate(PLANTS)]
    rng = random.Random(7)
    for k in range(24):
        s1, s2 = rng.uniform(0.8, 1.2), rng.uniform(0.85, 1.15)
        scale = dict(m_p=s1, l=s2, J=s1 * s2 * rng.uniform(0.95, 1.05), m_eff=rng.uniform(1.0, 1.2))
        sc = dict(delay=rng.uniform(*P.ACT_DELAY), tau=rng.uniform(0.0, P.PIVOT_FRICTION),
                  offset=rng.uniform(-P.ANGLE_OFFSET, P.ANGLE_OFFSET), counts=rng.choice((4096, 2400)))
        runs.append((scale, sc, PUSH if k % 2 == 0 else -PUSH, math.pi + rng.uniform(-0.05, 0.05)))
    return runs


ROBUST = _robust_runs()


def printed_grams(name):
    """Sliced mass (G-code) if the part has been sliced, else volume x density x FILL."""
    import structure as S
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
    import assembly as A
    import hardware as H
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
    return dict(m_cart=cart["m"], m_belt=belt, m_spin=j_spin / r ** 2, m_eff=m_eff, m_p=pend["m"], l=l, J=pend["J"],
                r=r, v_max=P.V_MAX, x_soft=P.X_SOFT / 1000.0, pend_parts=pend["parts"], cart_parts=cart["parts"])


def motor_force(v):
    """Force (N) the motor can put on the belt at cart speed v, at the driver's current and supply:
    the chopper holds the set current until back-EMF and the winding's inductance limit it."""
    mo, dr = P.MOTOR, P.DRIVE
    r = P.PD / 2000.0
    w = abs(v) / r
    kt = P.NEMA17["torque"] / (math.sqrt(2.0) * mo["i_rated"])          # N m per phase amp
    i = min(dr["i_set"], max(0.0, (dr["volts"] - kt * w) / math.hypot(mo["r"], mo["pole_pairs"] * w * mo["l"])))
    return kt * i / r


def friction():
    """Coulomb friction at the cart (N) and its parts. The idler turns on a plain PETG journal that
    both belt runs load."""
    f = P.FRICTION
    parts = dict(rails=f["rails"], belt=f["belt"],
                 idler=round(f["idler_mu"] * 2 * P.BELT_TENSION * P.IDLER_JOURNAL_R / (P.PD / 2), 3))
    return sum(parts.values()), parts


def lqr(m, q, r):
    """Continuous LQR on the upright linearisation, with integral action on the cart's position:
    state [x, v, theta, omega, integral of x], input = cart acceleration."""
    a = m["m_p"] * P.G_ACC * m["l"] / m["J"]
    b = m["m_p"] * m["l"] / m["J"]
    n = 5
    A_ = np.zeros((n, n))
    A_[0, 1] = A_[2, 3] = A_[4, 0] = 1.0
    A_[3, 2] = a
    B_ = np.array([[0.0], [1.0], [0.0], [-b], [0.0]])
    Q = np.diag(q)
    R = np.array([[r]])
    Hm = np.block([[A_, -B_ @ np.linalg.inv(R) @ B_.T], [-Q, -A_.T]])
    w, vecs = np.linalg.eig(Hm)
    st = vecs[:, w.real < 0]
    X = np.real(st[n:] @ np.linalg.inv(st[:n]))
    K = (np.linalg.inv(R) @ B_.T @ X).ravel()
    poles = np.linalg.eigvals(A_ - B_ @ K[None, :])
    return K, poles


def gains(m, cand):
    """The controller's numbers for a candidate, from the model the controller believes (m)."""
    K = lqr(m, cand["q"], cand["r"])[0]
    mgl = m["m_p"] * P.G_ACC * m["l"]
    return dict(K=[float(k) for k in K], dt=1.0 / CTRL_HZ, alpha=cand.get("alpha", 0.35), a_max=cand["a_max"],
                v_max=P.V_MAX, x_pump=cand.get("xp", 0.8) * P.X_SOFT / 1000.0,
                pump=cand["pump"], ks=cand.get("ks", 1.0), lead=cand.get("lead", 0.0), kx=cand["kx"], kv=cand["kv"],
                ke=cand["ke"], e_ref=cand["e_ref"],
                catch_cos=math.cos(math.radians(cand["catch"][0])), catch_xi=cand["catch"][1], fall=math.radians(45.0),
                mgl=mgl, J=m["J"], w0=math.sqrt(mgl / m["J"]), kick_a=cand["kick"][0],
                kick_n=int(round(cand["kick"][1] * CTRL_HZ)), wait_n=CTRL_HZ, still_w=0.3, still_n=CTRL_HZ // 4,
                z_max=2.0 / max(abs(float(K[4])), 1e-6), pred_n=int(cand.get("pred", 0)), a_lin=mgl / m["J"],
                b_lin=m["m_p"] * m["l"] / m["J"])


def _wrap(a):
    """To (-pi, pi]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a <= -math.pi:
        a += 2.0 * math.pi
    return a


class Controller:
    """One control period of the firmware (firmware/pendulum/controller.h: same names, same order).
    step(th, x, v): measured angle (rad, 0 upright, + leaning towards +x, any turn), cart position
    (m) and speed (m/s) -> cart acceleration to command (m/s^2). SWING: a kick when the pendulum
    rests near hanging, else energy pumping with cart centring. BALANCE: LQR plus the integral of x
    (it takes up an upright calibration error), on the state predicted over the pred_n commands
    still on their way to the motor (the step generator plans ahead). Timers count control
    periods, so that float and double arithmetic switch on the same period."""
    SWING, BALANCE = 0, 1
    HIST = 8

    def __init__(self, g):
        self.g = g
        self.reset()

    def reset(self):
        self.mode = self.SWING
        self.have_prev = False
        self.th_prev = self.w = self.z = 0.0
        self.kick = -1           # periods into a kick, -1: none
        self.wait = 0            # periods before another kick may start
        self.still = 0           # periods the pendulum has rested near hanging
        self.kick_dir = 1.0
        self.hist = [0.0] * self.HIST   # the last commands, oldest first

    def step(self, th_meas, x, v):
        g = self.g
        dt = g["dt"]
        if not self.have_prev:
            self.th_prev = th_meas
            self.have_prev = True
        d = _wrap(th_meas - self.th_prev)
        self.th_prev = th_meas
        self.w += g["alpha"] * (d / dt - self.w)
        th = _wrap(th_meas)
        w = self.w
        c = math.cos(th)
        if self.mode == self.BALANCE and abs(th) > g["fall"]:
            self.mode = self.SWING
            self.still = 0
        if self.mode == self.SWING and self.kick < 0 and c > g["catch_cos"] and abs(th + w / g["w0"]) < g["catch_xi"]:
            self.mode = self.BALANCE        # near the top and coasting into it: little left to correct
            self.z = 0.0
        if self.mode == self.BALANCE:
            K = g["K"]
            xp, vp, thp, wp = x, v, th, w
            n = g["pred_n"]
            for i in range(n):
                uq = self.hist[self.HIST - n + i]
                wp += (g["a_lin"] * thp - g["b_lin"] * uq) * dt
                thp += wp * dt
                xp += (vp + 0.5 * uq * dt) * dt
                vp += uq * dt
            u = -(K[0] * xp + K[1] * vp + K[2] * thp + K[3] * wp + K[4] * self.z)
            if abs(u) < g["a_max"]:
                self.z = min(g["z_max"], max(-g["z_max"], self.z + x * dt))
        elif self.kick >= 0:
            u = self.kick_dir * (g["kick_a"] if self.kick < g["kick_n"] else -g["kick_a"])
            self.kick += 1
            if self.kick >= 2 * g["kick_n"]:
                self.kick = -1
                self.wait = g["wait_n"]
        else:
            e = 0.5 * g["J"] * w * w + g["mgl"] * (c - 1.0 - g["e_ref"])
            fade = max(0.0, 1.0 - (x / g["x_pump"]) ** 2)      # no pumping near the travel ends
            # cart speed ~ -sin(theta), saturated (beats pivot friction at small swings) and led by
            # `lead` s (the cart's reversal lags): its acceleration ~ -omega cos(theta) pumps energy
            # in, while speed and travel stay bounded
            vt = (-g["pump"] * fade * math.tanh(-g["ke"] * e / g["mgl"])
                  * math.tanh(g["ks"] * math.sin(th + w * g["lead"])))
            u = g["kv"] * (vt - v) - g["kx"] * x
            if self.wait > 0:
                self.wait -= 1
            if c < -0.95 and abs(w) < g["still_w"] and self.wait == 0:
                self.still += 1
                if self.still >= g["still_n"]:          # at rest near hanging: kick, towards the centre
                    self.kick = 0
                    self.still = 0
                    self.kick_dir = -1.0 if x > 0.0 else 1.0
            else:
                self.still = 0
        u = min(g["a_max"], max(-g["a_max"], u))
        if (v >= g["v_max"] and u > 0.0) or (v <= -g["v_max"] and u < 0.0):
            u = 0.0
        self.hist.pop(0)
        self.hist.append(u)
        return u


def simulate(m, g, sc, t_end=T_END, push_at=PUSH_AT, push=PUSH, theta0=math.pi, record=False):
    """The controller `g` on plant `m` in scenario `sc` (delay, tau, offset, counts), from hanging
    still. Returns the outcome, and with record=True the 200 Hz log (t, x, v, theta, u, F, mode,
    measured angle)."""
    mp, l, J = m["m_p"], m["l"], m["J"]
    mgl, ml = mp * P.G_ACC * l, mp * l
    cvis, tau = 2e-4, sc["tau"]
    vmax = m["v_max"]
    dt = 1.0 / SIM_HZ
    h2, h6 = dt / 2.0, dt / 6.0
    n_sub = SIM_HZ // CTRL_HZ
    q = 2.0 * math.pi / sc["counts"]
    off = math.radians(sc["offset"])
    f_fric = friction()[0]
    safety = P.DRIVE["safety"]
    pipe = deque([0.0] * max(1, int(round(sc["delay"] * SIM_HZ))))
    ctl = Controller(g)
    sin, cos, tanh = math.sin, math.cos, math.tanh

    def acc(th, w, uu):
        return (mgl * sin(th) - ml * uu * cos(th) - cvis * w - tau * tanh(w * 50.0)) / J

    x = v = w = uu = 0.0
    th = theta0
    n = int(round(t_end * CTRL_HZ))
    k_push = int(round(push_at * CTRL_HZ)) if push_at is not None else -1
    t_bal, t_catch, bal_run, ever = None, None, 0, False
    x_max = v_max = f_max = height = 0.0
    margin = float("inf")
    log = [] if record else None
    for k in range(n):
        if k == k_push:
            t_catch = t_bal if ctl.mode == Controller.BALANCE else None
            w += push
        th_m = math.floor((th + off) / q + 0.5) * q
        x0, v0, th0 = x, v, th
        was = ctl.mode
        u = ctl.step(th_m, x, v)
        if ctl.mode == Controller.BALANCE:
            bal_run += 1
            ever = True
            if was != Controller.BALANCE:
                t_bal = k / CTRL_HZ
        else:
            bal_run = 0
        for _ in range(n_sub):
            pipe.append(u)
            uu = pipe.popleft()
            if (v >= vmax and uu > 0.0) or (v <= -vmax and uu < 0.0):
                uu = 0.0
            k1w = acc(th, w, uu)
            k2t, k2w = w + h2 * k1w, acc(th + h2 * w, w + h2 * k1w, uu)
            k3t, k3w = w + h2 * k2w, acc(th + h2 * k2t, w + h2 * k2w, uu)
            k4t, k4w = w + dt * k3w, acc(th + dt * k3t, w + dt * k3w, uu)
            th += h6 * (w + 2.0 * k2t + 2.0 * k3t + k4t)
            w += h6 * (k1w + 2.0 * k2w + 2.0 * k3w + k4w)
            x += v * dt + 0.5 * uu * dt * dt
            v += uu * dt
        wd = acc(th, w, uu)
        f_dyn = m["m_eff"] * uu + mp * (uu + l * (wd * cos(th) - w * w * sin(th)))
        margin = min(margin, motor_force(v) * safety - abs(f_dyn) - f_fric)
        f_max = max(f_max, abs(f_dyn))
        x_max = max(x_max, abs(x))
        v_max = max(v_max, abs(v))
        height = max(height, 0.5 + 0.5 * cos(th))
        if record:
            log.append((k / CTRL_HZ, x0, v0, _wrap(th0), u, f_dyn, ctl.mode, th_m))
    ok = bool(t_catch is not None and t_catch <= push_at - 1.0 and bal_run >= CTRL_HZ
              and x_max <= m["x_soft"] - X_MARGIN and margin >= 0.0)
    return dict(ok=ok, t_catch=t_catch, x_max=x_max, v_max=v_max, f_max=f_max, margin=margin, height=height,
                balanced=bool(ever), log=log)


def _plant(m, scale):
    p = dict(m)
    for k, f in scale.items():
        p[k] = p[k] * f
    return p


def evaluate(m, cand, stop_on_fail=False):
    """Every ROBUST run of a candidate, worst values over all of them. `partial` scores how far a
    failed run got (0..1), for the search."""
    g = gains(m, cand)
    ev = dict(runs=0, fails=[], x_max=0.0, t_worst=0.0, margin=float("inf"), f_max=0.0, v_max=0.0, partial=0.0)
    for k, (scale, sc, push, th0) in enumerate(ROBUST):
        r = simulate(_plant(m, scale), g, sc, push=push, theta0=th0)
        ev["runs"] += 1
        ev["x_max"] = max(ev["x_max"], r["x_max"])
        ev["t_worst"] = max(ev["t_worst"], r["t_catch"] if r["t_catch"] is not None else 99.0)
        ev["margin"] = min(ev["margin"], r["margin"])
        ev["f_max"] = max(ev["f_max"], r["f_max"])
        ev["v_max"] = max(ev["v_max"], r["v_max"])
        if not r["ok"]:
            ev["fails"].append(k)
            ev["partial"] = 0.4 * r["height"] + 0.3 * r["balanced"] + 0.3 * (r["t_catch"] is not None)
            if stop_on_fail:
                return ev
    return ev


def hunting(m, g):
    """Balanced, the pivot's Coulomb friction makes the pendulum hunt: while the bearing sticks the
    pendulum moves with the cart, and the balance law walks the cart until it breaks free. Peak-to-
    peak angle and cart travel against the friction (nominal otherwise), after 4 s of balancing,
    and a straight line through the origin for the firmware's f test."""
    rows = []
    for tau in HUNT_TAUS:
        r = simulate(m, g, dict(NOMINAL, tau=tau), t_end=10.0, push_at=None, theta0=0.02, record=True)
        log = np.array(r["log"], float)
        w = log[log[:, 0] >= 4.0]
        th = np.degrees(w[:, 3])
        rows.append(dict(pivot_mNm=round(tau * 1000.0, 3), theta_pp_deg=round(float(th.max() - th.min()), 2),
                         cart_pp_mm=round(float(w[:, 1].max() - w[:, 1].min()) * 1000.0, 1),
                         balanced=bool(np.all(w[:, 6] == Controller.BALANCE))))
    fit = [r for r in rows if r["pivot_mNm"] >= 0.5]
    s = sum(r["pivot_mNm"] ** 2 for r in fit)
    goal = next(r for r in rows if abs(r["pivot_mNm"] - P.PIVOT_FRICTION_GOAL * 1000.0) < 1e-9)
    return dict(table=rows, at_goal=goal,
                deg_per_mNm=round(sum(r["pivot_mNm"] * r["theta_pp_deg"] for r in fit) / s, 3),
                mm_per_mNm=round(sum(r["pivot_mNm"] * r["cart_pp_mm"] for r in fit) / s, 2))


# From tune_controller.py: LQR weights q on [x, v, theta, omega, integral of x] and r; acceleration
# limit; swing-up: cart speed amplitude pump (m/s), its sharpness on sin(theta) ks, speed loop kv
# (1/s) and centring kx (1/s^2), energy sharpness ke and target e_ref (of m g l above upright rest); catch (deg from upright, and
# the largest theta + omega / w0 in rad: coasting into the top); kick (m/s^2, s each way); pred:
# periods of commands still on their way to the motor that the balance law looks past; alpha:
# rate filter. Chosen from 74 candidates that pass every ROBUST run by 260 random scenarios none was
# tuned on (same bounds): 258 swung up, held and took the push; cart within +-146 mm.
CANDIDATES = [
    dict(q=(2580.071, 10.071, 109.237, 4.679, 25.581), r=1.385, a_max=4.68, pump=0.222, ks=15.345, lead=0.037, xp=1.935,
         kx=3.7, kv=31.766, ke=53.171, catch=(38.91, 0.133), e_ref=0.128, kick=(3.028, 0.067), pred=0, alpha=0.9),
]


def run(write=True, verbose=True):
    m = mass_model()
    best = None
    for cand in CANDIDATES:
        ev = evaluate(m, cand)
        key = (len(ev["fails"]), ev["margin"] < 0.0, ev["x_max"], ev["t_worst"])
        if best is None or key < best[0]:
            best = (key, cand, ev)
    _, cand, ev = best
    g = gains(m, cand)
    poles = lqr(m, cand["q"], cand["r"])[1]
    nom = simulate(m, g, NOMINAL, record=True)
    log = np.array(nom["log"], float)
    t_catch = nom["t_catch"]
    after = log[(log[:, 0] > (t_catch or 0) + 1.5) & (log[:, 0] < PUSH_AT)]
    f_total, f_parts = friction()
    spm = P.STEPS_PER_REV / (math.pi * P.PD) * 1000.0
    res = dict(
        masses=dict(cart_kg=round(m["m_cart"], 3), belt_kg=round(m["m_belt"], 3), spinning_kg=round(m["m_spin"], 3),
                    effective_kg=round(m["m_eff"], 3), pendulum_kg=round(m["m_p"], 4), cg_m=round(m["l"], 4),
                    J_kgm2=round(m["J"], 6), cart_parts=m["cart_parts"], pendulum_parts=m["pend_parts"]),
        limits=dict(a_max=cand["a_max"], v_max=P.V_MAX, x_soft_m=m["x_soft"], drive=dict(P.DRIVE),
                    motor_N={f"{v:g} m/s": round(motor_force(v), 2) for v in (0.0, 0.5, 1.0)},
                    friction_N=round(f_total, 2), friction_parts=f_parts),
        natural_rad_s=round(g["w0"], 3),
        controller=dict(q=list(cand["q"]), r=cand["r"], pump_m_s=cand["pump"], ks=g["ks"], lead_s=g["lead"],
                        kx=cand["kx"], kv=cand["kv"],
                        ke=cand["ke"], e_ref=cand["e_ref"], catch_deg=cand["catch"][0], catch_xi_rad=cand["catch"][1],
                        kick_m_s2=cand["kick"][0], kick_s=cand["kick"][1], z_max=round(g["z_max"], 4),
                        predict_periods=g["pred_n"], rate_filter=g["alpha"]),
        lqr_K=[round(float(k), 3) for k in g["K"]],
        lqr_poles=[[round(float(p.real), 3), round(float(p.imag), 3)] for p in poles],
        swing_up_s=None if t_catch is None else round(t_catch, 2),
        x_max_m=round(nom["x_max"], 4), v_max_m_s=round(nom["v_max"], 3), f_peak_N=round(nom["f_max"], 2),
        force_margin_N=round(nom["margin"], 2), balanced_at_end=nom["ok"],
        theta_rms_balanced_deg=round(float(np.degrees(np.sqrt(np.mean(after[:, 3] ** 2)))), 3) if len(after) else None,
        robust=dict(runs=ev["runs"], all_ok=not ev["fails"], fails=ev["fails"], x_max_m=round(ev["x_max"], 4),
                    swing_up_s=round(ev["t_worst"], 2), force_margin_N=round(ev["margin"], 2),
                    v_max_m_s=round(ev["v_max"], 3), frame_push_N=round(ev["f_max"], 2),
                    step_rate_hz=round(ev["v_max"] * spm)),
        scenarios=dict(nominal=NOMINAL, corners=CORNERS, plants=PLANTS),
        push_rad_s=PUSH, push_at_s=PUSH_AT, steps_per_mm=round(spm / 1000.0, 3), mm_per_rev=round(math.pi * P.PD, 3),
        hunting=hunting(m, g),
    )
    # the firmware's numbers (make_firmware.py writes them into config.h), to float precision
    res["firmware"] = {k: [float(f"{x:.7g}") for x in v] if isinstance(v, list) else
                       (v if isinstance(v, int) else float(f"{v:.7g}")) for k, v in g.items()}
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
        print(json.dumps({k: v for k, v in res.items() if k not in ("trajectory", "masses", "scenarios")}, indent=1))
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
    f_fric = res["limits"]["friction_N"]
    need = np.abs(log[:, 5]) + f_fric
    avail = np.array([motor_force(v) * P.DRIVE["safety"] for v in log[:, 2]])
    ax[2].plot(t, need, color="#555", label="force needed (motion + friction)")
    ax[2].plot(t, avail, color="#c0392b", lw=0.9, ls="--",
               label=f"motor can give ({P.DRIVE['safety']:.0%} of its torque at speed)")
    ax[2].set_ylim(0, max(avail.max(), need.max()) * 1.1)
    ax[2].set_ylabel("force (N)")
    ax[2].set_xlabel("time (s)")
    ax[2].legend(loc="lower right", fontsize=8)
    lq = log[:, 6] > 0.5
    for a in ax:
        a.fill_between(t, 0, 1, where=lq, transform=a.get_xaxis_transform(), color="#2ea44f", alpha=0.08)
        a.grid(alpha=0.25)
    fig.suptitle(f"From hanging still: kick, swing-up, caught at {res['swing_up_s']} s, pushed at {PUSH_AT:g} s "
                 f"(green: balancing)")
    fig.tight_layout()
    os.makedirs(os.path.join(G.ROOT, "renders"), exist_ok=True)
    fig.savefig(os.path.join(G.ROOT, "renders", "52_sim_swingup.png"), dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    run(write="--no-write" not in sys.argv)

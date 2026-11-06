"""Write firmware/pendulum/config.h from the design (params.py) and the tuned controller in
parts/sim.json, and test the firmware's controller: --test replays simulated runs through
firmware/pendulum/controller.h (compiled with the host's C++ compiler, or WSL's on Windows) and
compares every command with scripts/sim.py's Controller, then checks the f test's estimator on
simulated free swings. check_parts.py does both.

Run: python scripts/make_firmware.py [--test]
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import geom as G
import params as P

PATH = os.path.join(G.ROOT, "firmware", "pendulum", "config.h")
TEST_SRC = os.path.join(G.ROOT, "firmware", "test", "controller_test.cpp")
SIM_JSON = os.path.join(G.PARTS_DIR, "sim.json")
CXX_FLAGS = ["-std=gnu++11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-const-variable"]


def _f(v):
    s = f"{float(v):.7g}"
    if not any(ch in s for ch in ".en"):
        s += ".0"
    return s + "f"


def load():
    with open(SIM_JSON) as f:
        return json.load(f)


def render():
    s = load()
    g, hunt = s["firmware"], s["hunting"]
    spm = P.STEPS_PER_REV / (math.pi * P.PD) * 1000.0
    rows = [
        ("float", "CTL_PI", "3.14159265f", ""),
        ("int", "CTL_HZ", str(P.CTRL_HZ), "control loop"),
        ("float", "CTL_DT", _f(g["dt"]), "s"),
        ("float", "CTL_K[5]", "{" + ", ".join(_f(k) for k in g["K"]) + "}",
         "on x (m), v (m/s), angle (rad), rate (rad/s), integral of x (m s)"),
        ("float", "CTL_Z_MAX", _f(g["z_max"]), "integral clamp (m s)"),
        ("int", "CTL_PRED_N", str(int(g["pred_n"])), "periods of commands still on their way to the motor"),
        ("float", "CTL_A_LIN", _f(g["a_lin"]), "1/s^2: m g l / J, for the prediction"),
        ("float", "CTL_B_LIN", _f(g["b_lin"]), "1/m: m l / J"),
        ("float", "CTL_ALPHA", _f(g["alpha"]), "rate filter"),
        ("float", "CTL_A_MAX", _f(g["a_max"]), "m/s^2: what the motor can give with friction, at the driver's current"),
        ("float", "CTL_V_MAX", _f(g["v_max"]), "m/s"),
        ("float", "CTL_PUMP", _f(g["pump"]), "swing-up: cart speed amplitude (m/s), sharpness on sin and energy"),
        ("float", "CTL_KS", _f(g["ks"]), ""),
        ("float", "CTL_LEAD", _f(g["lead"]), "s: the pump looks this far ahead"),
        ("float", "CTL_X_PUMP", _f(g["x_pump"]), "m: the pump fades to nothing here"),
        ("float", "CTL_KE", _f(g["ke"]), ""),
        ("float", "CTL_KX", _f(g["kx"]), "cart centring (1/s^2) and speed loop (1/s) while swinging"),
        ("float", "CTL_KV", _f(g["kv"]), ""),
        ("float", "CTL_E_REF", _f(g["e_ref"]), "energy aimed at, of m g l above upright rest"),
        ("float", "CTL_MGL", _f(g["mgl"]), "N m: pendulum mass x g x CG distance"),
        ("float", "CTL_J", _f(g["J"]), "kg m^2 about the pivot"),
        ("float", "CTL_W0", _f(g["w0"]), "rad/s"),
        ("float", "CTL_CATCH_COS", _f(g["catch_cos"]), "catch within this angle (cosine)"),
        ("float", "CTL_CATCH_XI", _f(g["catch_xi"]), "and coasting into the top: |angle + rate / w0| below this (rad)"),
        ("float", "CTL_FALL", _f(g["fall"]), "back to swing-up past this angle (rad)"),
        ("float", "CTL_KICK_A", _f(g["kick_a"]), "kick from rest: m/s^2 for CTL_KICK_N periods each way"),
        ("int", "CTL_KICK_N", str(int(g["kick_n"])), ""),
        ("int", "CTL_WAIT_N", str(int(g["wait_n"])), "periods before another kick"),
        ("float", "CTL_STILL_W", _f(g["still_w"]), "rad/s: slower than this near hanging is resting"),
        ("int", "CTL_STILL_N", str(int(g["still_n"])), "periods at rest before a kick"),
        None,
        ("float", "CFG_STEPS_PER_M", _f(spm),
         f"1/{P.STEPS_PER_REV // 200} microstepping, {P.TEETH}-tooth HTD {P.BELT['pitch']:.0f}M pulley"),
        ("float", "CFG_X_SOFT", _f(P.X_SOFT / 1000.0), "m: the controller stops past this"),
        ("float", "CFG_X_SWITCH", _f(P.X_SWITCH / 1000.0), "m: the limit switches trip here"),
        ("float", "CFG_HOME_BACKOFF", _f((P.X_SWITCH - P.X_SOFT - 1.0) / 1000.0), "m: back off the switch after homing"),
        ("float", "CFG_HOME_SPEED", _f(0.03), "m/s"),
        ("int", "CFG_PLANNING_MS", "10", "step planner look-ahead: part of the delay sim.py allows for"),
        ("int", "CFG_COUNTS_AS5600", "4096", ""),
        ("int", "CFG_COUNTS_ENCODER", "2400", "600 P/R: both edges of both channels"),
        ("float", "CFG_PIVOT_GOAL", _f(P.PIVOT_FRICTION_GOAL), "N m: the f test's goal for the pivot's friction"),
        ("float", "CFG_PIVOT_MAX", _f(P.PIVOT_FRICTION), "N m: the swing-up is checked up to this"),
        ("float", f"CFG_HUNT_MNM[{len(hunt['table'])}]", "{" + ", ".join(_f(r["pivot_mNm"]) for r in hunt["table"]) + "}",
         "balanced, the pendulum hunts (sim.py) at this pivot friction, mN m:"),
        ("float", f"CFG_HUNT_DEG[{len(hunt['table'])}]", "{" + ", ".join(_f(r["theta_pp_deg"]) for r in hunt["table"]) + "}",
         "deg peak to peak"),
        ("float", f"CFG_HUNT_MM[{len(hunt['table'])}]", "{" + ", ".join(_f(r["cart_pp_mm"]) for r in hunt["table"]) + "}",
         "cart mm peak to peak"),
    ]
    out = ["// Generated by scripts/make_firmware.py from scripts/params.py and parts/sim.json: do not edit.",
           "// Change the design or the controller there, then run python scripts/build_all.py.",
           "#pragma once", "", "// controller (scripts/sim.py, Controller)"]
    for row in rows:
        if row is None:
            out += ["", "// machine (scripts/params.py)"]
            continue
        typ, name, val, note = row
        line = f"static const {typ} {name} = {val};"
        out.append(f"{line:<46s}  // {note}" if note else line)
    return "\n".join(out) + "\n"


def current():
    if not os.path.exists(PATH):
        return None
    with open(PATH, encoding="utf-8") as f:
        return f.read()


def vectors():
    """Simulated control periods, run with the config's own numbers: angle, x, v -> command, mode."""
    import sim
    s = load()
    ms = s["masses"]
    m = dict(m_p=ms["pendulum_kg"], l=ms["cg_m"], J=ms["J_kgm2"], m_eff=ms["effective_kg"], v_max=P.V_MAX,
             x_soft=P.X_SOFT / 1000.0)
    out = []
    for sc in (sim.NOMINAL, sim.CORNERS[0], sim.CORNERS[1]):
        r = sim.simulate(m, s["firmware"], sc, record=True)
        out.append("# " + json.dumps(sc))
        out += [f"{thm!r},{x!r},{v!r},{u!r},{mode}" for t, x, v, th, u, f, mode, thm in r["log"]]
    return "\n".join(out) + "\n"


def _compiler():
    """('native', path) or ('wsl', path) or (None, None)."""
    for c in ("g++", "clang++", "c++"):
        p = shutil.which(c)
        if p:
            return "native", p
    if os.name == "nt" and shutil.which("wsl"):
        try:
            r = subprocess.run(["wsl", "-e", "sh", "-c", "command -v g++"], capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and r.stdout.strip():
                return "wsl", r.stdout.strip().splitlines()[-1]
        except (OSError, subprocess.SubprocessError):
            pass
    return None, None


def controller_test():
    """Compile firmware/test/controller_test.cpp and replay vectors() through controller.h.
    Returns (status, detail), status 'pass', 'fail' or 'skipped'."""
    kind, cxx = _compiler()
    if kind is None:
        return "skipped", "controller test skipped: no C++ compiler here (CI runs it)"
    tmp = tempfile.mkdtemp(prefix="pendulum-fw-")
    try:
        vec = os.path.join(tmp, "vectors.csv")
        with open(vec, "w", newline="\n") as f:
            f.write(vectors())
        exe = os.path.join(tmp, "controller_test")
        if kind == "native":
            build, run = [cxx, *CXX_FLAGS, "-o", exe, TEST_SRC], [exe, vec]
        else:
            def wsl(p):
                return subprocess.run(["wsl", "-e", "wslpath", "-a", p], capture_output=True, text=True,
                                      timeout=120).stdout.strip()
            build = ["wsl", "-e", cxx, *CXX_FLAGS, "-o", wsl(exe), wsl(TEST_SRC)]
            run = ["wsl", "-e", wsl(exe), wsl(vec)]
        r = subprocess.run(build, capture_output=True, text=True, timeout=600)
        if r.returncode:
            return "fail", "compile: " + (r.stderr or r.stdout).strip()[-800:]
        r = subprocess.run(run, capture_output=True, text=True, timeout=600)
        res = [json.loads(line) for line in r.stdout.splitlines() if line.startswith("{")]
        if r.returncode or not res or res[-1]["mismatches"] or res[-1].get("pivot_bad", 1):
            return "fail", (r.stdout.strip() or r.stderr.strip())[-800:]
        res = res[-1]
        return "pass", (f"{res['steps']} control periods of {res['runs']} simulated runs replayed through controller.h "
                        f"({'WSL ' if kind == 'wsl' else ''}{os.path.basename(cxx)}, float): the same commands "
                        f"(largest difference {res['worst_du']:.1e} m/s^2, {res['worst_ratio']:.0%} of the tolerance) "
                        f"and modes; the f test on {res['pivot_cases']} simulated free swings: pivot friction within "
                        f"{res['pivot_tau_err_mNm']:.2f} mN m, vertical within {res['pivot_centre_err_deg']:.3f} deg")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print("wrote firmware/pendulum/config.h")
    if "--test" in sys.argv:
        status, detail = controller_test()
        print(f"controller test: {status}: {detail}")
        return status != "fail"
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

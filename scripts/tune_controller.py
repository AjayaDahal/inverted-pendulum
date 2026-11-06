"""Search for the controller's numbers (sim.py's CANDIDATES). A candidate must swing the pendulum up
from hanging still, hold it and take a push on every sim.ROBUST run, inside the soft limits and
the force budget; among those, the less it hunts when balanced (pivot stick-slip at the goal
friction and twice it), the better. Random search, then a local search around the best; prints
the best as CANDIDATES entries to paste into sim.py (after a check on scenarios they were not
tuned on: AGENTS.md).

Run: python scripts/tune_controller.py [random_n] [local_n] [seed]     (every core but one)
"""
import math
import multiprocessing as mp
import random
import sys
import time

import numpy as np

import params as P
import sim


def _log_uniform(rng, a, b):
    return math.exp(rng.uniform(math.log(a), math.log(b)))


def sample(rng):
    lu = _log_uniform
    a_max = round(rng.uniform(3.0, P.A_MAX), 2)
    return dict(q=(round(lu(rng, 30, 5000), 1), round(lu(rng, 3, 500), 1), round(lu(rng, 10, 500), 1),
                   round(lu(rng, 0.1, 20), 2), round(lu(rng, 1, 3000), 1)),
                r=round(lu(rng, 0.2, 20), 2), a_max=a_max, pump=round(rng.uniform(0.15, 0.7), 3),
                ks=round(lu(rng, 1, 30), 2), lead=round(rng.uniform(0.0, 0.12), 3), xp=round(rng.uniform(0.7, 2.5), 2),
                kx=round(lu(rng, 0.5, 20), 2),
                kv=round(lu(rng, 3, 40), 2),
                ke=round(lu(rng, 3, 100), 1),
                catch=(round(rng.uniform(8, 35), 1), round(lu(rng, 0.02, 0.6), 3)), e_ref=round(rng.uniform(0, 0.15), 3),
                kick=(round(rng.uniform(1.5, a_max), 2), round(rng.uniform(0.08, 0.2), 3)), pred=rng.randint(0, 4),
                alpha=round(rng.uniform(0.15, 0.6), 3))


def perturb(rng, c, s=0.25):
    def f(v, lo=None, hi=None, digits=3):
        v = v * math.exp(rng.gauss(0, s))
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return round(v, digits)
    a_max = f(c["a_max"], 2.0, P.A_MAX, 2)
    return dict(q=tuple(f(v) for v in c["q"]), r=f(c["r"]), a_max=a_max, pump=f(c["pump"], 0.05, 0.95),
                ks=f(c.get("ks", 1.0), 0.5, 60), lead=round(min(0.2, max(0.0, c.get("lead", 0.0) + rng.gauss(0, 0.015))), 3),
                xp=f(c.get("xp", 0.8), 0.5, 4.0),
                kx=f(c["kx"]), kv=f(c["kv"]), ke=f(c["ke"], 1, 200),
                catch=(f(c["catch"][0], 4, 40), f(c["catch"][1], 0.01, 1.0)),
                e_ref=f(max(c["e_ref"], 0.005), 0, 0.3), kick=(f(c["kick"][0], 0.5, a_max), f(c["kick"][1], 0.03, 0.3)),
                pred=min(5, max(0, c.get("pred", 0) + rng.choice((-1, 0, 0, 0, 1)))),
                alpha=f(c.get("alpha", 0.35), 0.08, 0.9))


_M = None


def _init(m):
    global _M
    _M = m


def _hunt(cand):
    """Balanced from near upright: peak-to-peak angle (deg) after 4 s at the pivot's goal friction,
    plus half that at twice it; 99 for a fall."""
    g, out = sim.gains(_M, cand), 0.0
    for tau, w in ((P.PIVOT_FRICTION_GOAL, 1.0), (2 * P.PIVOT_FRICTION_GOAL, 0.5)):
        log = np.array(sim.simulate(_M, g, dict(sim.NOMINAL, tau=tau), t_end=10.0, push_at=None, theta0=0.02,
                                    record=True)["log"], float)
        late = log[log[:, 0] >= 4.0]
        th = np.degrees(late[:, 3])
        out += w * (float(th.max() - th.min()) if np.all(late[:, 6] == sim.Controller.BALANCE) else 99.0)
    return out


def _score(cand):
    ev = sim.evaluate(_M, cand, stop_on_fail=True)
    ev["hunt"] = 0.0 if ev["fails"] else _hunt(cand)
    return cand, ev


def key(ev):
    passed = ev["runs"] - len(ev["fails"])
    return (len(ev["fails"]) > 0, -(passed + ev["partial"]), ev["hunt"], ev["x_max"], ev["t_worst"], -ev["margin"])


def search(pool, cands, label):
    t0 = time.time()
    out = []
    for i, (cand, ev) in enumerate(pool.imap_unordered(_score, cands, chunksize=2)):
        out.append((key(ev), cand, ev))
        if not ev["fails"]:
            print(f"  {label} pass: x {ev['x_max'] * 1000:.0f} mm, catch <= {ev['t_worst']:.2f} s, "
                  f"margin {ev['margin']:.2f} N, hunting {ev['hunt']:.2f}  {cand}", flush=True)
        if (i + 1) % 200 == 0:
            print(f"  {label}: {i + 1}/{len(cands)} in {time.time() - t0:.0f} s", flush=True)
    out.sort(key=lambda r: r[0])
    return out


def main():
    n_rand = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    n_local = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    m = sim.mass_model()
    print(f"{len(sim.ROBUST)} runs per candidate", flush=True)
    with mp.Pool(max(1, mp.cpu_count() - 1), initializer=_init, initargs=(m,)) as pool:
        res = search(pool, sim.CANDIDATES + [sample(rng) for _ in range(n_rand)], "random")
        for rnd in range(3):
            base = [c for _, c, _ in res[:8]]
            res2 = search(pool, [perturb(rng, base[i % len(base)], (0.3, 0.15, 0.07)[rnd])
                                 for i in range(n_local // 3)], f"local {rnd + 1}")
            res = sorted(res + res2, key=lambda r: r[0])
    print("\nBest (paste the top ones into sim.py CANDIDATES):")
    for k, cand, ev in res[:6]:
        print(f"# fails {len(ev['fails'])}, runs {ev['runs']} (partial {ev['partial']:.2f}), x {ev['x_max'] * 1000:.0f} mm, "
              f"catch <= {ev['t_worst']:.2f} s, margin {ev['margin']:.2f} N, hunting {ev['hunt']:.2f} deg")
        print(f"dict(q={cand['q']}, r={cand['r']}, a_max={cand['a_max']}, pump={cand['pump']}, ks={cand.get('ks', 1.0)}, "
              f"lead={cand.get('lead', 0.0)}, xp={cand.get('xp', 0.8)}, "
              f"kx={cand['kx']}, kv={cand['kv']}, ke={cand['ke']}, catch={cand['catch']}, e_ref={cand['e_ref']}, "
              f"kick={cand['kick']}, pred={cand.get('pred', 0)}, alpha={cand.get('alpha', 0.35)}),")


if __name__ == "__main__":
    main()

"""Service layer: turns optimiser runs into JSON-friendly results for the API/frontend."""
from functools import lru_cache
import numpy as np
from .model import generate_instance, solve

PRICES = [0, 50, 100, 200, 500, 1000, 2000, 5000]  # USD per tCO2e

class InfeasibleError(ValueError):
    pass

def _pct(s, b):
    return 100 * (s["cost"] / b["cost"] - 1), 100 * (s["carbon"] / b["carbon"] - 1)

@lru_cache(maxsize=16)
def _ctx(seed, jobs, cap):
    inst = generate_instance(seed, n_jobs=jobs, cap=cap)
    base = solve(inst, 1, 0, "home", "asap")
    cmin, kmin = solve(inst, 1, 0, "all", "flex"), solve(inst, 0, 1, "all", "flex")
    if base is None or cmin is None or kmin is None:
        raise InfeasibleError("Instance is infeasible: increase capacity or reduce jobs.")
    return inst, base, cmin, kmin

def scenarios(seed=0, jobs=80, cap=200):
    inst, base, cmin, kmin = _ctx(seed, jobs, cap)
    a, b = 1 / cmin["cost"], 1 / cmin["carbon"]
    runs = [("Status quo", base),
            ("Delay jobs only", solve(inst, a, b, "home", "flex")),
            ("Move across clouds only", solve(inst, a, b, "all", "asap")),
            ("Move and delay (balanced)", solve(inst, a, b, "all", "flex")),
            ("Cheapest possible", cmin), ("Cleanest possible", kmin)]
    return [[n, *(round(v, 2) for v in _pct(s, base))] for n, s in runs]

def frontier(seed=0, jobs=80, cap=200, points=11):
    inst, base, cmin, kmin = _ctx(seed, jobs, cap)
    out = []
    for eps in np.linspace(kmin["carbon"], cmin["carbon"], points):
        s = solve(inst, 1, 0, "all", "flex", carbon_cap=eps * 1.0000001)
        if s:
            c, k = _pct(s, base); out.append([round(k, 2), round(c, 2)])
    return out  # [carbon %, cost %] ordered cleanest -> cheapest

def price_sweep(seed=0, jobs=80, cap=200):
    inst, base, _, _ = _ctx(seed, jobs, cap)
    clean = int(np.argmin(inst.ci.mean(axis=1)))
    out = []
    for p in PRICES:
        s = solve(inst, 1, p / 1000, "all", "flex")
        c, k = _pct(s, base)
        out.append([p, round(c, 2), round(k, 2), round(100 * float(s["share"][clean]), 1)])
    return out  # [USD/tCO2e, cost %, carbon %, % work in cleanest region]

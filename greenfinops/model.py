"""Joint cost + carbon scheduling across multi-cloud regions (LP formulation).

Decision x[j,r,t] = vCPU-hours of job j run in region r during hour t.
  min   a * sum(cost * x) + b * sum(carbon * x)
  s.t.  sum_{r,t} x[j,r,t] = D_j                (job demand met)
        sum_j x[j,r,t]     <= Cap_r             (regional capacity)
        0 <= x[j,r,t]      <= maxrate_j         (parallelism limit)
        x only defined inside the job's [release, deadline] window
  cost   = price[r,t] + egress[home_j,r] * data_j / D_j        ($ / vCPU-h)
  carbon = kW_vcpu * PUE_r * CI[r,t] / 1000                   (kgCO2e / vCPU-h)
All data are SYNTHETIC and illustrative (see README).
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack

KW_PER_VCPU = 0.012  # ~12 W per vCPU, all-in server share (assumption)

REGIONS = [  # name, provider, mean CI (g/kWh), price mult, PUE, UTC offset, CI diurnal amp
    ("A-us-east", "A", 380, 1.00, 1.15, -5.0, 0.25),
    ("A-eu-north", "A", 30, 1.10, 1.10, 1.0, 0.08),
    ("B-us-west", "B", 150, 1.04, 1.12, -8.0, 0.35),
    ("B-eu-west", "B", 300, 1.08, 1.12, 0.0, 0.20),
    ("C-ap-south", "C", 700, 0.93, 1.30, 5.5, 0.20),
]

@dataclass
class Instance:
    names: list; providers: list; T: int
    ci: np.ndarray; price: np.ndarray; pue: np.ndarray; cap: np.ndarray
    egress: np.ndarray; jobs: list

def generate_instance(seed=0, n_jobs=80, T=72, cap=200):
    rng = np.random.default_rng(seed)
    R = len(REGIONS); t = np.arange(T)
    ci = np.zeros((R, T)); price = np.zeros((R, T))
    for i, (_, _, m, pm, _, off, amp) in enumerate(REGIONS):
        loc = t + off
        ci[i] = m * (1 + amp * np.cos(2 * np.pi * (loc - 1) / 24)) * (1 + 0.06 * rng.standard_normal(T))
        price[i] = 0.04 * pm * (1 + 0.18 * np.sin(2 * np.pi * (loc - 9) / 24)) * (1 + 0.03 * rng.standard_normal(T))
    prov = [r[1] for r in REGIONS]
    eg = np.zeros((R, R))
    for a in range(R):
        for b in range(R):
            if a != b:
                eg[a, b] = 0.02 if prov[a] == prov[b] else 0.09
    jobs = []
    for j in range(n_jobs):
        D = float(np.clip(rng.lognormal(np.log(150), 0.7), 20, 1500))
        m = float(rng.uniform(20, 60)); D = min(D, m * 30)
        dur = int(np.ceil(D / m))
        deferrable = rng.random() < 0.7
        slack = int(rng.integers(8, 31)) if deferrable else 2
        rel = int(rng.integers(0, 37))
        jobs.append(dict(id=j, home=int(rng.integers(0, R)), rel=rel, D=D, m=m,
                         end_flex=min(T - 1, rel + dur + slack),
                         end_asap=min(T - 1, rel + dur + 2),
                         gb=float(np.clip(rng.lognormal(np.log(50), 0.8), 1, 800)),
                         deferrable=deferrable))
    return Instance([r[0] for r in REGIONS], prov, T, ci, price,
                    np.array([r[4] for r in REGIONS]), np.full(R, float(cap)), eg, jobs)

def solve(inst, a=1.0, b=0.0, regions="all", time="flex", carbon_cap=None):
    """regions: 'all' | 'home'; time: 'flex' | 'asap'. Returns dict or None if infeasible."""
    R, T = len(inst.names), inst.T
    J, Rr, Tt, cc, kc = [], [], [], [], []
    for j in inst.jobs:
        end = j["end_flex"] if time == "flex" else j["end_asap"]
        for r in ([j["home"]] if regions == "home" else range(R)):
            for tt in range(j["rel"], end + 1):
                J.append(j["id"]); Rr.append(r); Tt.append(tt)
                cc.append(inst.price[r, tt] + inst.egress[j["home"], r] * j["gb"] / j["D"])
                kc.append(KW_PER_VCPU * inst.pue[r] * inst.ci[r, tt] / 1000)
    J, Rr, Tt, cc, kc = map(np.array, (J, Rr, Tt, cc, kc))
    n = len(J); idx = np.arange(n)
    A_eq = coo_matrix((np.ones(n), (J, idx)), shape=(len(inst.jobs), n)).tocsr()
    b_eq = np.array([j["D"] for j in inst.jobs])
    rows = [coo_matrix((np.ones(n), (Rr * T + Tt, idx)), shape=(R * T, n)).tocsr()]
    b_ub = [np.repeat(inst.cap, T)]
    if carbon_cap is not None:
        rows.append(coo_matrix(kc.reshape(1, -1))); b_ub.append([carbon_cap])
    A_ub = vstack(rows).tocsr(); b_ub = np.concatenate(b_ub)
    ub = np.array([inst.jobs[j]["m"] for j in J])
    res = linprog(a * cc + b * kc, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=np.column_stack([np.zeros(n), ub]), method="highs")
    if res.status != 0:
        return None
    x = res.x
    return dict(cost=float(cc @ x), carbon=float(kc @ x), x=x, J=J, R=Rr, T=Tt,
                share=np.bincount(Rr, weights=x, minlength=R) / x.sum())

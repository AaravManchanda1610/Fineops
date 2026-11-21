import numpy as np, pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from greenfinops import generate_instance, solve

def metrics(s, base): return dict(cost=s["cost"], carbon=s["carbon"],
    d_cost=100*(s["cost"]/base["cost"]-1), d_carbon=100*(s["carbon"]/base["carbon"]-1))

rows, fronts, prices = [], [], []
for seed in range(10):
    inst = generate_instance(seed)
    base = solve(inst, 1, 0, "home", "asap")
    cmin = solve(inst, 1, 0, "all", "flex"); kmin = solve(inst, 0, 1, "all", "flex")
    Cref, Kref = cmin["cost"], cmin["carbon"]
    scen = {"Status quo (home, no deferral)": base,
            "Temporal only (home, deferral)": solve(inst, 1/Cref, 1/Kref, "home", "flex"),
            "Spatial only (multi-cloud, no deferral)": solve(inst, 1/Cref, 1/Kref, "all", "asap"),
            "Joint balanced (multi-cloud + deferral)": solve(inst, 1/Cref, 1/Kref, "all", "flex"),
            "Joint cost-only": cmin, "Joint carbon-only": kmin}
    for k, s in scen.items(): rows.append(dict(seed=seed, scenario=k, **metrics(s, base)))
    for eps in np.linspace(kmin["carbon"], cmin["carbon"], 15):
        s = solve(inst, 1, 0, "all", "flex", carbon_cap=eps*1.0000001)
        fronts.append(dict(seed=seed, **metrics(s, base)))
    for pi in [0, 50, 100, 200, 500, 1000, 2000, 5000]:  # $/tCO2e
        s = solve(inst, 1, pi/1000, "all", "flex")
        prices.append(dict(seed=seed, carbon_price=pi, **metrics(s, base), share_nordic=s["share"][1]*100))
df, fr, pr = pd.DataFrame(rows), pd.DataFrame(fronts), pd.DataFrame(prices)
summ = df.groupby("scenario")[["d_cost", "d_carbon"]].agg(["mean", "std"]).round(2)
psum = pr.groupby("carbon_price")[["d_cost", "d_carbon", "share_nordic"]].mean().round(2)
summ.to_csv("results/scenario_summary.csv"); psum.to_csv("results/carbon_price_sweep.csv")
df.to_csv("results/raw_scenarios.csv", index=False); fr.to_csv("results/pareto_frontiers.csv", index=False)
fm = fr.groupby(fr.groupby("seed").cumcount())[["d_cost", "d_carbon"]].mean()
# marginal abatement cost along mean frontier (USD per tCO2e)
b0 = df[df.scenario.str.startswith("Status")].groupby("seed")[["cost", "carbon"]].mean().mean()
print(summ.to_string()); print(psum.to_string())
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
for sd, g in fr.groupby("seed"): ax[0].plot(g.d_carbon, g.d_cost, color="grey", alpha=.25)
ax[0].plot(fm.d_carbon, fm.d_cost, "o-", color="seagreen", label="Mean Pareto frontier")
ax[0].axhline(0, color="k", lw=.5); ax[0].set_xlabel("Carbon vs status quo (%)"); ax[0].set_ylabel("Cost vs status quo (%)")
ax[0].set_title("Cost-carbon Pareto frontier (10 seeds)"); ax[0].legend()
ax[1].plot(psum.index, psum.d_carbon, "s-", label="Carbon change (%)"); ax[1].plot(psum.index, psum.d_cost, "o-", label="Cost change (%)")
ax[1].set_xscale("symlog", linthresh=50); ax[1].set_xlabel("Internal carbon price (USD/tCO2e)"); ax[1].set_title("Effect of internal carbon price"); ax[1].legend()
plt.tight_layout(); plt.savefig("results/pareto_and_carbon_price.png", dpi=150)
# marginal abatement cost between cost-only and carbon-only
m = df.pivot(index="seed", columns="scenario", values=["cost", "carbon"])
mac = (m["cost"]["Joint carbon-only"] - m["cost"]["Joint cost-only"]) / (m["carbon"]["Joint cost-only"] - m["carbon"]["Joint carbon-only"]) * 1000
print("Mean avg abatement cost USD/tCO2e:", round(mac.mean(), 1), "+/-", round(mac.std(), 1))

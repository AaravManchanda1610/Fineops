# Green FinOps Optimiser

Reference implementation for the survey *"A Systematic Survey on Green FinOps: Jointly Optimising Financial Cost and
Carbon Footprint in Multi-Cloud Infrastructures"* (IILM University, Greater Noida).

It models workload placement and time-shifting across 5 regions and 3 cloud providers as a linear programme, and exposes
it through a REST API and a web dashboard.

## Architecture

    public/index.html  --fetch-->  api/index.py (Flask)  -->  greenfinops/service.py  -->  greenfinops/model.py (LP, HiGHS)

| Endpoint | Returns |
|---|---|
| `GET /api/health` | liveness check |
| `GET /api/scenarios` | six strategies (status quo, delay only, move only, balanced, cheapest, cleanest) as % change vs baseline |
| `GET /api/frontier?points=11` | cost-carbon Pareto frontier (epsilon-constraint sweep) |
| `GET /api/price_sweep` | effect of an internal carbon price (USD 0 to 5,000 per tCO2e) |

Shared query parameters: `seed` (0-999), `jobs` (10-150), `cap` (100-400, vCPUs per region-hour).
The dashboard calls these endpoints and falls back to bundled sample results if the API is unreachable.

## Run locally

    pip install -r requirements-dev.txt
    pytest -q
    python api/index.py          # open http://localhost:5000
    python run_experiment.py     # 10-seed study -> results/*.csv and charts

## Deploy to Vercel

    npm i -g vercel
    vercel login
    vercel --prod                # run from this folder

Or push the folder to GitHub and import the repository in the Vercel dashboard (framework preset: Other).
`vercel.json` sets a 30 s function timeout and bundles the `greenfinops` package; `public/` is served as the static site.
`requirements.txt` is deliberately minimal (flask, numpy, scipy) to stay within Vercel's function size limit.

## Data and limitations

Data are synthetic and illustrative: diurnal carbon-intensity and price profiles, generic Providers A/B/C.
Replace `generate_instance` in `greenfinops/model.py` with real inputs (grid carbon APIs such as Electricity Maps or
WattTime, cloud billing exports in FOCUS format, provider carbon reports). Results show the shape of the trade-off,
not real-world magnitudes. Not modelled: latency, SLAs, data residency, embodied carbon, forecast uncertainty.

Extensions: MILP for non-preemptible jobs, embodied carbon, SLA constraints, stochastic forecasts, RL policies.

## Layout

    api/index.py              Flask API (Vercel entrypoint)
    greenfinops/model.py      instance generator + LP solver
    greenfinops/service.py    scenario, frontier and carbon-price logic
    public/index.html         dashboard
    run_experiment.py         10-seed study for the paper
    tests/                    model and API tests
    vercel.json, .vercelignore, requirements*.txt

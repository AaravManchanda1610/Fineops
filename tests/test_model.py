from greenfinops import generate_instance, solve

def test_demand_and_capacity():
    inst = generate_instance(1); s = solve(inst, 1, 1)
    for j in inst.jobs: assert abs(s["x"][s["J"] == j["id"]].sum() - j["D"]) < 1e-5
    for r in range(len(inst.names)):
        for t in range(inst.T): assert s["x"][(s["R"] == r) & (s["T"] == t)].sum() <= inst.cap[r] + 1e-6

def test_extremes_ordered():
    inst = generate_instance(2)
    c, k = solve(inst, 1, 0), solve(inst, 0, 1)
    assert c["cost"] <= k["cost"] + 1e-6 and k["carbon"] <= c["carbon"] + 1e-6

def test_flexibility_never_hurts():
    inst = generate_instance(3)
    assert solve(inst, 1, 0, "all", "flex")["cost"] <= solve(inst, 1, 0, "home", "asap")["cost"] + 1e-6

def test_api_endpoints():
    import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
    from index import app
    c = app.test_client()
    assert c.get("/api/health").status_code == 200
    sc = c.get("/api/scenarios").get_json()["scenarios"]
    assert sc[0][1:] == [0.0, 0.0] and len(sc) == 6
    assert len(c.get("/api/frontier?points=7").get_json()["points"]) == 7
    assert len(c.get("/api/price_sweep").get_json()["sweep"]) == 8
    assert c.get("/api/scenarios?jobs=9999").status_code == 400

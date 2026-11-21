"""Flask API (Vercel serverless entrypoint). Run locally: python api/index.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flask import Flask, jsonify, request, send_from_directory
from greenfinops import service

ROOT = os.path.join(os.path.dirname(__file__), "..", "public")
app = Flask(__name__)

def arg(name, default, lo, hi):
    try: v = int(request.args.get(name, default))
    except ValueError: raise ValueError(f"'{name}' must be an integer")
    if not lo <= v <= hi: raise ValueError(f"'{name}' must be between {lo} and {hi}")
    return v

def params():
    return dict(seed=arg("seed", 0, 0, 999), jobs=arg("jobs", 80, 10, 150), cap=arg("cap", 200, 100, 400))

def reply(fn, **extra):
    try:
        data = fn(**params(), **extra)
    except service.InfeasibleError as e:
        return jsonify(error=str(e)), 422
    except ValueError as e:
        return jsonify(error=str(e)), 400
    r = jsonify(data)
    r.headers["Cache-Control"] = "public, s-maxage=3600"  # results are deterministic
    return r

@app.get("/api/health")
def health(): return jsonify(status="ok")

@app.get("/api/scenarios")
def scenarios(): return reply(lambda **k: dict(scenarios=service.scenarios(**k)))

@app.get("/api/frontier")
def frontier():
    try: pts = arg("points", 11, 5, 15)
    except ValueError as e: return jsonify(error=str(e)), 400
    return reply(lambda **k: dict(points=service.frontier(**k, points=pts)))

@app.get("/api/price_sweep")
def price_sweep(): return reply(lambda **k: dict(sweep=service.price_sweep(**k)))

@app.get("/")  # local dev only; on Vercel static files in /public are served directly
def index(): return send_from_directory(ROOT, "index.html")

if __name__ == "__main__":
    app.run(port=5000, debug=False)

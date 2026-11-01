"""Resumable runner for the pearls lab (copied from the Ali2 lab). Each (config, day) backtest is
appended to cache.jsonl as soon as it finishes. The cache key includes a hash of pearls_lab.py."""
import hashlib, json, os, re, shutil, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
LAB = os.path.dirname(os.path.abspath(__file__)); WORK = os.path.abspath(os.path.join(LAB, ".."))
CACHE = os.path.join(LAB, "cache.jsonl")
PRODUCTS = ["WHITE_PEARLS", "BLACK_PEARLS", "GOLDEN_PEARLS", "PINK_PEARLS", "BLUE_PEARLS"]
DAYS3 = [1, 2, 3]; HALVES = [11, 12, 21, 22, 31, 32]; PSHIFT = [41, 42, 43, 51, 52, 53]
GSTEP = [61, 62, 63, 71, 72, 73]; MIRROR = [81, 82, 83]
WRONG = [91, 92, 93, 94, 95, 96, 97, 98, 99]
ALL = DAYS3 + HALVES + PSHIFT + GSTEP + MIRROR
_lock = threading.Lock()
shutil.copy(os.path.join(LAB, "pearls_lab.py"), os.path.join(WORK, "strategies", "pearls.py"))
sys.path.insert(0, WORK)
from strategies.pearls import PearlStrategy
DEFAULTS = PearlStrategy.DEFAULTS

def norm(p, v):
    full = {**DEFAULTS[p], **(v or {})}
    if full.get("kind") != "sepehr":
        return dict(v)
    return {k: x for k, x in (v or {}).items() if DEFAULTS[p].get(k) != x}
def vkey(v): return json.dumps(v, sort_keys=True)
def tag(): return hashlib.md5(open(os.path.join(LAB, "pearls_lab.py"), "rb").read()).hexdigest()[:8]
def load_cache():
    out = {}
    if os.path.exists(CACHE):
        for line in open(CACHE): r = json.loads(line); out[r["key"]] = r
    return out
def run_one(cfg, day):
    env = dict(os.environ, PEARL_PARAMS=json.dumps(cfg))
    out = subprocess.run([sys.executable, "backtest.py", "--only", "pearls", "--days", str(day)], cwd=WORK, env=env, capture_output=True, text=True)
    rows = {m.group(1): int(m.group(2).replace(",", "")) for m in re.finditer(r"^(\w+)\s+([-\d,]+)\s+[-\d,]+\s*$", out.stdout, re.M)}
    if "TOTAL" not in rows and "day" not in out.stdout:
        raise RuntimeError(f"backtest failed {cfg} day {day}:\n{out.stdout[-1500:]}{out.stderr[-1500:]}")
    return {p: rows.get(p, 0) for p in PRODUCTS}, ("WARNING" in out.stdout or "crashed" in out.stdout)
def evaluate(variants, days=ALL, workers=14):
    """variants = {product: [variant dict, ...]} -> {product: {vkey: {day: pnl}}}"""
    variants = {p: [norm(p, v) for v in vs] for p, vs in variants.items()}
    n = max(len(vs) for vs in variants.values())
    cfgs = [{p: vs[i] for p, vs in variants.items() if i < len(vs) and vs[i]} for i in range(n)]
    cfgs = list({vkey(c): c for c in cfgs}.values())
    t, cache = tag(), load_cache()
    jobs = [(c, d) for c in cfgs for d in days if f"{t}|{d}|{vkey(c)}" not in cache]
    if jobs: print(f"running {len(jobs)} backtests", flush=True)
    def work(job):
        c, d = job; pnl, warn = run_one(c, d)
        rec = {"key": f"{t}|{d}|{vkey(c)}", "cfg": c, "day": d, "pnl": pnl, "warning": warn}
        with _lock:
            with open(CACHE, "a") as f: f.write(json.dumps(rec) + "\n")
            cache[rec["key"]] = rec
        return rec
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(work, jobs), 1):
            if i % 200 == 0: print(f"  {i}/{len(jobs)}", flush=True)
    out = {}
    for c in cfgs:
        for d in days:
            rec = cache[f"{t}|{d}|{vkey(c)}"]
            if rec["warning"]: print(f"WARNING (crash or limit cancel) in {c} day {d}")
            for p in variants: out.setdefault(p, {}).setdefault(vkey(c.get(p, {})), {})[d] = rec["pnl"][p]
    return out

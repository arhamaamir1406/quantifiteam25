"""Resumable runner for the Ali2 lab. Every (config, day) backtest is appended to cache.jsonl as
soon as it finishes, so a shutdown loses nothing. The cache key includes a hash of core_lab.py.

Ali's 6 products never interact (separate positions, separate memory), so one backtest can test a
different variant for each product at once: evaluate() zips each product's variant list into runs
and reads every product's own PnL row back out.
"""
import hashlib, json, os, re, shutil, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor

LAB = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.abspath(os.path.join(LAB, ".."))
sys.path.insert(0, WORK)
CACHE = os.path.join(LAB, "cache.jsonl")
PRODUCTS = ["AMETHYST", "TOFFEE_CAKE", "PAPER_LANTERNS", "TELLURIUM", "JELLY", "PEANUT_BUTTER"]
DAYS3 = [1, 2, 3]
HALVES = [11, 12, 21, 22, 31, 32]
SHIFT = [41, 42, 43, 51, 52, 53]
STEP = [61, 62, 63, 71, 72, 73]
MIRROR = [81, 82, 83]
ALL = DAYS3 + HALVES + SHIFT + STEP + MIRROR
_lock = threading.Lock()


def defaults():
    shutil.copy(os.path.join(LAB, "core_lab.py"), os.path.join(WORK, "strategies", "core.py"))
    sys.modules.pop("strategies.core", None)
    from strategies.core import CoreStrategy
    return CoreStrategy.DEFAULTS


DEFAULTS = defaults()


def norm(product, v):
    """A variant as only what differs from Ali's original (Ali's original itself = {})."""
    return {k: x for k, x in (v or {}).items() if DEFAULTS[product].get(k) != x}


def vkey(v):
    return json.dumps(v, sort_keys=True)


def tag():
    return hashlib.md5(open(os.path.join(LAB, "core_lab.py"), "rb").read()).hexdigest()[:8]


def load_cache():
    out = {}
    if os.path.exists(CACHE):
        for line in open(CACHE):
            r = json.loads(line)
            out[r["key"]] = r
    return out


def run_one(cfg, day):
    env = dict(os.environ, CORE_PARAMS=json.dumps(cfg))
    out = subprocess.run([sys.executable, "backtest.py", "--only", "core", "--days", str(day)],
                         cwd=WORK, env=env, capture_output=True, text=True)
    rows = {m.group(1): int(m.group(2).replace(",", ""))
            for m in re.finditer(r"^(\w+)\s+([-\d,]+)\s+[-\d,]+\s*$", out.stdout, re.M)}
    if "TOTAL" not in rows and "day" not in out.stdout:
        raise RuntimeError(f"backtest failed {cfg} day {day}:\n{out.stdout[-1500:]}{out.stderr[-1500:]}")
    return {p: rows.get(p, 0) for p in PRODUCTS}, ("WARNING" in out.stdout)


def evaluate(variants, days=ALL, workers=14):
    """variants = {product: [variant dict, ...]}. Returns {product: {vkey: {day: pnl}}}."""
    variants = {p: [norm(p, v) for v in vs] for p, vs in variants.items()}
    n = max(len(vs) for vs in variants.values())
    cfgs = [{p: vs[i] for p, vs in variants.items() if i < len(vs) and vs[i]} for i in range(n)]
    cfgs = list({vkey(c): c for c in cfgs}.values())
    t, cache = tag(), load_cache()
    jobs = [(c, d) for c in cfgs for d in days if f"{t}|{d}|{vkey(c)}" not in cache]
    if jobs:
        print(f"running {len(jobs)} backtests", flush=True)

    def work(job):
        c, d = job
        pnl, warn = run_one(c, d)
        rec = {"key": f"{t}|{d}|{vkey(c)}", "cfg": c, "day": d, "pnl": pnl, "warning": warn}
        with _lock:
            with open(CACHE, "a") as f:
                f.write(json.dumps(rec) + "\n")
            cache[rec["key"]] = rec
        return rec

    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(work, jobs), 1):
            if i % 100 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    out = {}
    for c in cfgs:
        for d in days:
            rec = cache[f"{t}|{d}|{vkey(c)}"]
            if rec["warning"]:
                print(f"WARNING (crash or limit cancel) in {c} day {d}")
            for p in variants:
                out.setdefault(p, {}).setdefault(vkey(c.get(p, {})), {})[d] = rec["pnl"][p]
    return out


if __name__ == "__main__":  # sanity check: Ali's original on days -2/-1/0
    r = evaluate({p: [{}] for p in PRODUCTS}, DAYS3)
    for p in PRODUCTS:
        print(p, r[p]["{}"])

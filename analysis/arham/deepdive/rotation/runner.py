"""Resumable backtest runner for the rotation tests (Steps 1-2, Oct 30 2026).

Each (params, day) result is appended to cache.jsonl the moment it finishes, so a crash or
shutdown loses nothing: rerunning skips everything already in the cache. The cache key includes
a hash of fruit_lychee_EXPERIMENT.py, so editing the strategy never reuses stale results.

Backtests run in a scratch copy of the repo (WORK) with the experiment file dropped in as
strategies/fruit_lychee.py and the params passed through the FL_PARAMS environment variable.
"""
import hashlib, json, os, re, shutil, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
WORK = os.environ.get("ROT_WORK", os.path.join(os.environ.get("TEMP", "/tmp"), "quantifi_rotation_work"))
EXPERIMENT = os.path.join(HERE, "fruit_lychee_EXPERIMENT.py")
CACHE = os.path.join(HERE, "cache.jsonl")
DAYS = (-2, -1, 0)
BASE = {-2: 60720, -1: 62807, 0: 58256}  # committed strategy (181,784)
_lock = threading.Lock()


def setup():
    os.makedirs(os.path.join(WORK, "strategies"), exist_ok=True)
    for f in ("backtest.py", "datamodel.py", "trader.py"):
        shutil.copy(os.path.join(REPO, f), WORK)
    for f in os.listdir(os.path.join(REPO, "strategies")):
        if f.endswith(".py"):
            shutil.copy(os.path.join(REPO, "strategies", f), os.path.join(WORK, "strategies"))
    if not os.path.isdir(os.path.join(WORK, "data")):
        shutil.copytree(os.path.join(REPO, "data"), os.path.join(WORK, "data"))
    shutil.copy(EXPERIMENT, os.path.join(WORK, "strategies", "fruit_lychee.py"))


def tag():
    return hashlib.md5(open(EXPERIMENT, "rb").read()).hexdigest()[:8]


def key(params, day):
    return f"{tag()}|{day}|{json.dumps(params, sort_keys=True)}"


def load_cache():
    out = {}
    if os.path.exists(CACHE):
        for line in open(CACHE):
            r = json.loads(line)
            out[r["key"]] = r
    return out


def run_one(params, day):
    env = dict(os.environ, FL_PARAMS=json.dumps(params))
    out = subprocess.run([sys.executable, "backtest.py", "--only", "fruit_lychee", "--days", str(day)],
                         cwd=WORK, env=env, capture_output=True, text=True).stdout
    rows = {}
    for m in re.finditer(r"^(\w+)\s+([-\d,]+)\s+[-\d,]+\s*$", out, re.M):
        rows[m.group(1)] = int(m.group(2).replace(",", ""))
    if "TOTAL" not in rows:
        raise RuntimeError(f"backtest failed for {params} day {day}:\n{out[-2000:]}")
    return {"total": rows["TOTAL"], "lychee": rows.get("LYCHEE", 0),
            "vouchers": sum(v for k, v in rows.items() if k.startswith("VOUCHER_")),
            "crash": "WARNING" in out}


def run_all(param_list, days=DAYS, workers=14):
    """Returns {(json params, day): result} for every combination, running only what's missing."""
    setup()
    cache = load_cache()
    jobs = [(p, d) for p in param_list for d in days if key(p, d) not in cache]
    if jobs:
        print(f"running {len(jobs)} backtests ({len(param_list) * len(days) - len(jobs)} cached)", flush=True)

    def work(job):
        p, d = job
        r = run_one(p, d)
        rec = {"key": key(p, d), "params": p, "day": d, **r}
        with _lock:
            with open(CACHE, "a") as f:
                f.write(json.dumps(rec) + "\n")
            cache[rec["key"]] = rec
        return rec

    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(work, jobs), 1):
            if i % 50 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)
    return {(json.dumps(p, sort_keys=True), d): cache[key(p, d)] for p in param_list for d in days}


if __name__ == "__main__":  # sanity check: defaults must reproduce the committed 181,784
    res = run_all([{}])
    print({d: res[("{}", d)]["total"] for d in DAYS}, "expected", BASE)

import json, os, re, subprocess, sys, itertools
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
def run(params):
    env = dict(os.environ, FL_PARAMS=json.dumps(params))
    out = subprocess.run([sys.executable, "backtest.py", "--only", "fruit_lychee"], cwd=HERE, env=env,
                         capture_output=True, text=True).stdout
    def row(name):
        m = re.search(rf"^{name}\s+([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)\s+([-\d,]+)", out, re.M)
        return [int(v.replace(",", "")) for v in m.groups()] if m else None
    return params, row("TOTAL"), row("LYCHEE")
def grid(space):
    keys = list(space); combos = [dict(zip(keys, v)) for v in itertools.product(*space.values())]
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(run, combos))
if __name__ == "__main__":
    space = json.loads(sys.argv[1])
    base = [60720, 62807, 58256]
    res = grid(space)
    res.sort(key=lambda r: -(r[1][0] + r[1][1]))  # rank by TRAINING days only
    print("params | change vs current on day -2, day -1 (training) | day 0 (unseen) | LYCHEE own pnl")
    for p, tot, ly in res:
        d = [t - b for t, b in zip(tot, base)]
        print(f"{json.dumps(p):70s} train {d[0]:+7,} {d[1]:+7,} | day0 {d[2]:+7,} | lychee {ly[:3] if ly else '-'}")

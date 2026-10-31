"""Step 2 data check: does any voucher sit CONSISTENTLY above or below the fitted smile?

Replays the bot's own smile (parabola fit across strikes, EMA half-life 200) over each day and
records every strike's residual = market mid - Black-Scholes price at the smile vol (in coins).
If a strike's average residual has the same sign and similar size on all 3 days, the model is
missing a per-strike offset. If it flips sign or is tiny, there's nothing to add.

Run from the repo root:  python analysis/arham/deepdive/rotation/offsets.py
"""
import csv, math, os, sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
from strategies.fruit_lychee import FruitLycheeStrategy as F  # noqa: E402

HL = 200


def day_residuals(day):
    mids = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(ROOT, "data", f"prices_day_{day}.csv")), delimiter=";"):
        mids[int(r["timestamp"])][r["product"]] = float(r["mid_price"])
    smile, n = None, 0
    res = defaultdict(list)  # sym -> [(t, residual coins)]
    for t in sorted(mids):
        S = mids[t].get("LYCHEE")
        if not S:
            continue
        T = max(5 - t / 1_000_000, 0.1)
        xs, ivs = {}, {}
        for sym, K in F.VOUCHERS.items():
            m = mids[t].get(sym)
            if not m:
                continue
            x = 100 * math.log(K / S) / math.sqrt(T)
            guess = smile[0] + smile[1] * x + smile[2] * x * x if smile else 0.02
            iv = F.implied_vol(m, S, K, T, guess)
            xs[sym] = x
            if iv is not None:
                ivs[sym] = iv
        if len(ivs) >= 5:
            fit = F.fit_parabola([xs[s] for s in ivs], list(ivs.values()))
            if fit is not None:
                n += 1
                a = max(1 - 0.5 ** (1 / HL), 1 / n)
                smile = fit if smile is None else [o + a * (f - o) for o, f in zip(smile, fit)]
        if smile is None:
            continue
        for sym, x in xs.items():
            vol = smile[0] + smile[1] * x + smile[2] * x * x
            res[sym].append((t, mids[t][sym] - F.bs_call(S, F.VOUCHERS[sym], T, vol)))
    return res


def autocorr(v, lag):
    a, b = v[:-lag], v[lag:]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


if __name__ == "__main__":
    out = {d: day_residuals(d) for d in (-2, -1, 0)}
    print("Average residual (market mid - smile price) in coins, per day; then its std and how")
    print("much of it is still there 1000 / 3000 ticks later (autocorrelation, all days pooled)")
    print(f"{'strike':<14}{'day -2':>8}{'day -1':>8}{'day 0':>8}{'std':>7}{'ac1000':>8}{'ac3000':>8}")
    for sym in F.VOUCHERS:
        means, allv, acs = [], [], {1000: [], 3000: []}
        for d in (-2, -1, 0):
            v = [r for _, r in out[d][sym]]
            means.append(sum(v) / len(v))
            allv += v
            for lag in acs:
                acs[lag].append(autocorr(v, lag))  # one list entry per tick
        sd = (sum((x - sum(allv) / len(allv)) ** 2 for x in allv) / len(allv)) ** 0.5
        print(f"{sym:<14}" + "".join(f"{m:>8.2f}" for m in means) + f"{sd:>7.2f}"
              + "".join(f"{sum(a) / len(a):>8.2f}" for a in acs.values()))

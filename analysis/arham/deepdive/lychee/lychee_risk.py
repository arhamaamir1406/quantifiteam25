import math, random, statistics as st
from load import load
mids, book, trades = load()
full = []
for d in (-2, -1, 0): full += [mids[d]["LYCHEE"][t] for t in sorted(mids[d]["LYCHEE"])]
anchor = st.mean(full); start = full[-1]
step = st.pstdev([full[i + 10] - full[i] for i in range(0, len(full) - 10, 10)])   # per 10 ticks
def fade_pnl(path, n=200, w=60):
    pnl = 0.0
    for i in range(len(path) - 1):
        tgt = -n * max(-1, min(1, (path[i] - anchor) / w)); pnl += tgt * (path[i + 1] - path[i])
    return pnl
def sim(kind, hl=1500):
    v = start; path = [v]; b = 0.5 ** (10 / hl)
    for _ in range(1000):
        if kind == "ou": v = anchor + (v - anchor) * b + random.gauss(0, step)
        else: v += random.gauss(0, step)
        path.append(v)
    return fade_pnl(path)
random.seed(7)
print(f"anchor for the scoring day (mean of all 3 days) {anchor:.0f}, day 0 closed at {start:.0f}, 10-tick sd {step:.2f}")
actual = [fade_pnl([mids[d]['LYCHEE'][t] for t in sorted(mids[d]['LYCHEE'])][::10]) for d in (-2, -1, 0)]
print("directional fade PnL on the real days (no costs, instant fills):", [round(a) for a in actual])
for kind in ("rw", "ou"):
    r = sorted(sim(kind) for _ in range(2000))
    print(f"{'NO leash (random walk)' if kind == 'rw' else 'leash is real (OU, half-life 1500)':36s}: mean {st.mean(r):+7.0f}  sd {st.pstdev(r):6.0f}  "
          f"5th pct {r[100]:+7.0f}  1st pct {r[20]:+7.0f}  P(loss>10K) {sum(x < -10000 for x in r) / len(r):.0%}  P(gain) {sum(x > 0 for x in r) / len(r):.0%}")

"""Fast mid-price sim of a LYCHEE fade (crossing the spread to trade, so costs are pessimistic)."""
import math, statistics as st, itertools
from load import load
mids, book, trades = load()
days = (-2, -1, 0)
B = {d: [(book[d]["LYCHEE"][t][0][0][0], book[d]["LYCHEE"][t][1][0][0]) for t in sorted(book[d]["LYCHEE"])] for d in days}
PRIOR = st.mean([ (b + a) / 2 for d in (-2, -1) for b, a in B[d]])   # anchor learned from training days only

def run(day, anchor_kind, H, W, N, band=5):
    pos, cash = 0, 0.0; anc = None; cm_n = 0
    for b, a in B[day]:
        m = (b + a) / 2
        if anchor_kind == "fixed": anc = PRIOR
        elif anchor_kind == "ema": anc = PRIOR if anc is None else anc + (m - anc) * (1 - 0.5 ** (1 / H))
        elif anchor_kind == "cum":  # running mean, starting from PRIOR with weight H ticks
            cm_n += 1; anc = PRIOR if anc is None else anc + (m - anc) / (H + cm_n)
        tgt = int(round(-N * max(-1, min(1, (m - anc) / W))))
        if abs(tgt - pos) >= band:
            q = tgt - pos
            cash -= q * (a if q > 0 else b); pos = tgt
    b, a = B[day][-1]
    return cash + pos * (b + a) / 2

print(f"anchor learned from days -2/-1: {PRIOR:.1f}")
rows = []
for kind, H in [("fixed", 0), ("ema", 1000), ("ema", 3000), ("ema", 10000), ("cum", 5000), ("cum", 20000)]:
    for W, N in itertools.product((20, 40, 60, 90), (50, 100, 200)):
        tr = [run(d, kind, H, W, N) for d in (-2, -1)]
        rows.append((sum(tr), kind, H, W, N, tr))
rows.sort(reverse=True)
print("TOP 8 settings on the TRAINING days, then the same settings on day 0 (unseen):")
for s, kind, H, W, N, tr in rows[:8]:
    print(f"  {kind:5s} H={H:5d} W={W:3d} N={N:3d}: train {tr[0]:+8.0f} {tr[1]:+8.0f}  ->  day 0 {run(0, kind, H, W, N):+8.0f}")
print("Median over ALL settings tried: train/day", f"{st.median(r[0] for r in rows)/2:+.0f}", " day 0", f"{st.median(run(0, r[1], r[2], r[3], r[4]) for r in rows):+.0f}")
print("Share of settings that make money on day 0:", f"{sum(run(0, r[1], r[2], r[3], r[4]) > 0 for r in rows) / len(rows):.0%}")

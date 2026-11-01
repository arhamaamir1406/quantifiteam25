"""Round 2: fine neighbourhoods, 3-way rotation and wrong-world downside, all 33 test days.
Columns (absolute PnL, not vs Sepehr): days -2/-1/0, 3-day total, half-days (positive count, worst),
mirrored total, PINK-sum-shifted total, GOLDEN-step total, then the product's own wrong-world days."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import evaluate, ALL, WRONG, DAYS3, HALVES, MIRROR, PSHIFT, GSTEP
S = lambda **k: {"kind": "saw", "exit_take": 1, **k}
G = lambda **k: {"kind": "slide", "ride": 20, **k}
V = {
 "PINK_PEARLS": [{}] + [{"kind": "sum", "take": t, "make": m, "w": w, "tgt_window": tw}
                        for t in (1, 2, 3) for m in (1, 2) for w in (0.5, 0.75, 1.0) for tw in (2000, 5000, 10000)],
 "BLUE_PEARLS": [{}] + [S(n=n, trig=t, quiet=q, bounce=q, drift_pos=d, smin=s)
                        for n, t in ((5, 8), (10, 12), (10, 14), (15, 15)) for q in (6, 10, 15) for d in (10, 20) for s in (0.01, 0.03)]
   + [S(n=10, trig=12, quiet=10, bounce=10, drift_pos=20, sw=w) for w in (1000, 8000)]
   + [S(n=10, trig=12, quiet=10, bounce=10, drift_pos=20, slip=2), S(n=10, trig=12, quiet=10, bounce=10, drift_pos=20, ride=10),
      S(n=10, trig=12, quiet=10, bounce=10, drift_pos=0)],
 "GOLDEN_PEARLS": [{}] + [G(guard=g, quiet=q, cap=c, slip=s) for g in (2, 3, 4) for q in (3, 6, 12) for c in (3, 5, 10) for s in (0, 2)],
 "BLACK_PEARLS": [{}, {"kind": "join", "cap": 1}, {"kind": "join", "cap": 2}, {"kind": "join", "cap": 3}],
}
OWN_WRONG = {"BLUE_PEARLS": [91, 92, 93], "PINK_PEARLS": [94, 95, 96], "GOLDEN_PEARLS": [97, 98, 99], "BLACK_PEARLS": [91, 92, 93]}

def report(p, res, top=30):
    rows = []
    for k, r in res.items():
        three = [r[d] for d in DAYS3]; halves = [r[d] for d in HALVES]; wr = [r[d] for d in OWN_WRONG[p]]
        rows.append((sum(three), f"{k[:84]:<84}" + "".join(f"{x:>7,}" for x in three) + f"{sum(three):>8,} | "
                     f"{sum(x > 0 for x in halves)}/6 {min(halves):>6,} | {sum(r[d] for d in MIRROR):>7,} {sum(r[d] for d in PSHIFT):>7,} {sum(r[d] for d in GSTEP):>7,} | "
                     + "".join(f"{x:>7,}" for x in wr) + f"{sum(wr):>8,}"))
    rows.sort(key=lambda x: -x[0])
    out = [f"\n=== {p}", f"{'variant':<84}{'d-2':>7}{'d-1':>7}{'d0':>7}{'3-day':>8} | halves worst | mirror  shift+-  Gstep | own wrong-world days (abs) total"]
    out += [r for _, r in rows[:top]]
    # rotation: pick the best on 2 days, score the held-out one
    out.append(f"  rotation (pick best on the other 2 days -> held-out day):")
    for h in DAYS3:
        train = [d for d in DAYS3 if d != h]
        best = max(res, key=lambda k: sum(res[k][d] for d in train))
        out.append(f"    held-out {h}: picks {best[:80]} -> {res[best][h]:,} (Sepehr {res['{}'][h]:,})")
    return "\n".join(out)

if __name__ == "__main__":
    res = evaluate(V, ALL + WRONG)
    text = "\n".join(report(p, res[p]) for p in V)
    print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "round2_results.txt"), "w").write(text)

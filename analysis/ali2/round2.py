"""Round 2: fine neighbourhoods around each round-1 winner, plus the 3-way rotation
(pick the variant with the best TRAINING days, score it on the held-out day).
For JELLY / PEANUT_BUTTER (no edge) we also print the risk of each option: worst segment and
spread of PnL over the 3 days + 6 half-days.
"""
import io, json, os, statistics as st, sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import DAYS3, HALVES, evaluate, vkey  # noqa: E402
from report import table  # noqa: E402

ROT = {1: (2, 3), 2: (1, 3), 3: (1, 2)}  # held-out day -> training days (1,2,3 = days -2,-1,0)
NAME = {1: "day -2", 2: "day -1", 3: "day 0"}

V = {
    "TOFFEE_CAKE": [{}] + [{"mode": "hybrid", "win": w, "take": t} for w in (3000, 4000, 5000, 6000) for t in (8, 10)]
    + [{"mode": "hybrid", "win": w, "kind": "around", "take": t, "make": 4} for w in (3000, 4000, 5000, 6000)
       for t in (8, 10)],
    "PAPER_LANTERNS": [{}] + [{"kind": "momo", "k": k, "look": lk} for k in (0.5, 0.75, 1.0) for lk in (50, 100, 150, 200)]
    + [{"kind": "momo", "k": 0.75, "look": 100, "take": t} for t in (1, 3)]
    + [{"kind": "momo", "k": 0.75, "look": 100, "n": n} for n in (10, 30)],
    "TELLURIUM": [{}] + [{"kind": "join", "cap": c} for c in (3, 4, 5, 6, 7, 8)],
    "JELLY": [{}] + [{"kind": "join", "cap": c} for c in (1, 2, 3, 4, 5)]
    + [{"cap": c, "size": 2} for c in (3, 5)],
    "PEANUT_BUTTER": [{}] + [{"kind": "join", "cap": c} for c in (1, 2, 3, 4, 5)]
    + [{"cap": c, "size": 2, "edge": 4} for c in (3, 5)],
}


def rotation(res, keys):
    lines = []
    total = 0
    for test, train in ROT.items():
        best = max(keys, key=lambda k: sum(res[k][d] for d in train))
        g = res[best][test] - res["{}"][test]
        total += g
        lines.append(f"   held-out {NAME[test]:>6}: training picks {best} -> {res[best][test]:,} "
                     f"(Ali {res['{}'][test]:,}, {g:+,})")
    lines.append(f"   => picking by training days beats Ali by {total:+,} on held-out days")
    return "\n".join(lines)


def risk(product, res):
    lines = [f"\n--- {product} risk (absolute PnL over the 3 days + 6 half-days)",
             f"{'variant':<44}{'mean':>8}{'sd':>8}{'worst':>8}{'best':>8}"]
    for k, r in res.items():
        seg = [r[d] for d in DAYS3 + HALVES]
        lines.append(f"{k:<44}{st.mean(seg):>8,.0f}{st.pstdev(seg):>8,.0f}{min(seg):>8,}{max(seg):>8,}")
    return "\n".join(lines)


if __name__ == "__main__":
    res = evaluate(V)
    buf = io.StringIO()
    with redirect_stdout(buf):
        for p in V:
            print(table(p, res[p], toffee=(p == "TOFFEE_CAKE")))
            keys = [vkey(v) for v in res[p] and [json.loads(k) for k in res[p]] if v]
            print(rotation(res[p], [k for k in res[p] if k != "{}"]))
            if p in ("JELLY", "PEANUT_BUTTER"):
                print(risk(p, res[p]))
    text = buf.getvalue()
    print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "round2_results.txt"), "w").write(text)

"""Round 1: every candidate from our research vs Ali's original, on all 24 test days.
Columns: PnL on days -2/-1/0, then for each test group "days beaten / total gain vs Ali",
the worst single-day loss vs Ali, and the total gain vs Ali over all test days.
"""
import io, os, sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import evaluate  # noqa: E402
from report import table  # noqa: E402

FX = {"mode": "fixed"}
V = {
    "AMETHYST": [{}, {"kind": "join", "cap": 50}, {"kind": "join", "cap": 30}, {"kind": "join", "cap": 20},
                 {"kind": "around", "take": 1, "make": 1}, {"kind": "around", "take": 1, "make": 2},
                 {"kind": "around", "take": 2, "make": 1}],
    "TOFFEE_CAKE": [{}, FX] + [{"mode": "hybrid", "win": w} for w in (1000, 2000, 4000, 8000)]
    + [{"win": w} for w in (2000, 4000)]
    + [{**FX, "kind": "around", "take": t, "make": m} for t, m in ((8, 4), (6, 3), (10, 5), (8, 6))]
    + [{"mode": "hybrid", "win": 4000, "kind": "around", "take": 8, "make": 4}]
    + [{**FX, "edge": e} for e in (4, 5, 7)] + [{**FX, "take": t} for t in (6, 7, 10)]
    + [{**FX, "size": s} for s in (5, 20, 50)] + [{**FX, "skew": s} for s in (0, 0.05, 0.2)],
    "PAPER_LANTERNS": [{}] + [{"fk": f} for f in (0.75, 1.5, 3.0)] + [{"gain": g} for g in (5, 20)]
    + [{"chase": c} for c in (5, 30)]
    + [{"kind": "momo", "k": k} for k in (0.5, 0.75, 1.0)]
    + [{"kind": "momo", "k": 0.75, "n": 40}, {"kind": "momo", "k": 0.75, "take": 1},
       {"kind": "momo", "k": 0.75, "take": 3}, {"kind": "momo", "k": 0.75, "look": 100},
       {"kind": "momo", "k": 0.75, "look": 300}],
    "TELLURIUM": [{}] + [{"kind": "join", "cap": c} for c in (3, 5, 8, 10, 15)]
    + [{"fg": 0.0}, {"cap": 5}, {"edge": 5}, {"edge": 6}],
    "JELLY": [{}, {"kind": "off"}] + [{"kind": "join", "cap": c} for c in (1, 2, 3, 5, 10)]
    + [{"size": 2, "cap": 5}, {"edge": 6}, {"edge": 6, "cap": 10}],
    "PEANUT_BUTTER": [{}, {"kind": "off"}] + [{"kind": "join", "cap": c} for c in (1, 2, 3, 5, 10)]
    + [{"size": 2, "cap": 5}, {"edge": 4}, {"edge": 4, "cap": 5}],
}

if __name__ == "__main__":
    res = evaluate(V)
    buf = io.StringIO()
    with redirect_stdout(buf):
        for p in V:
            print(table(p, res[p], toffee=(p == "TOFFEE_CAKE")))
    text = buf.getvalue()
    print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "round1_results.txt"), "w").write(text)

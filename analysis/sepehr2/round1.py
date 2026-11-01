"""Round 1: research candidates vs Sepehr's pushed version, all 24 test days."""
import io, os, sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import evaluate
from report import table
J = lambda c: {"kind": "join", "cap": c}
V = {
 "PINK_PEARLS": [{}] + [J(c) for c in (3, 5, 10)]
   + [{"kind": "sum", "take": t, "make": m, "w": w, "tgt_window": tw}
      for t in (1, 2, 3, 4) for m in (1, 2, 3) for w in (1.0, 0.75, 0.5) for tw in (0, 5000)],
 "GOLDEN_PEARLS": [{}, {"kind": "off"}] + [J(c) for c in (2, 3, 5, 10)]
   + [{"kind": "level", "fast": f, "take": t, "make": m, "guard": g, "cap": c}
      for f in (5, 20) for t in (1, 2) for m in (1, 2) for g in (3, 6) for c in (5, 20)],
 "WHITE_PEARLS": [{}, {"kind": "off"}] + [J(c) for c in (1, 2, 3, 5, 10)]
   + [{"cap": c} for c in (1, 2, 3)] + [{"threshold": 99}, {"skew": 0.5}],
 "BLACK_PEARLS": [{}, {"kind": "off"}] + [J(c) for c in (1, 2, 3, 5, 10)]
   + [{"cap": c, "size": c, "mode": "make", "edge": 1} for c in (1, 2, 3, 5)],
 "BLUE_PEARLS": [{}, {"kind": "off"}] + [J(c) for c in (1, 2, 3, 5, 10)]
   + [{"cap": c, "size": c, "mode": "make", "edge": 1} for c in (1, 2, 3, 5)]
   + [{"kind": "momo", "ema": e, "look": l, "k": k, "take": t, "make": 1, "cap": c}
      for e in (3, 8) for l in (5, 10) for k in (1.0, 2.0) for t in (2, 3) for c in (5, 20)],
}
if __name__ == "__main__":
    res = evaluate(V)
    buf = io.StringIO()
    with redirect_stdout(buf):
        for p in V: print(table(p, res[p]))
    text = buf.getvalue(); print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "round1_results.txt"), "w").write(text)

"""Step 1b: 3-way rotation test of the voucher settings (LYCHEE lean OFF, i.e. the committed bot).

For each setting we sweep its value with everything else at the committed default. In each
rotation the value with the best TRAINING-day total is "picked", and we report what that pick
does on the held-out day compared with the committed value. A setting is solid when the
committed value is at or near the top on every rotation and no alternative wins all 3 held-out days.
Writes step1_vouchers_results.txt next to this file.
"""
import io, json, os, sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import run_all  # noqa: E402

ROTATIONS = {-2: (-1, 0), -1: (-2, 0), 0: (-2, -1)}
DEFAULT = {"enter": 3.5, "exit": 1.5, "smile_halflife": 200, "flow_weight": 0.3, "flow_halflife": 30,
           "delta_skew": 0.05, "skew_cap": 5.0}
SWEEPS = {
    "smile_halflife": [50, 100, 200, 400, 800],
    "flow_weight": [0.0, 0.15, 0.3, 0.45, 0.6, 0.8],
    "flow_halflife": [10, 20, 30, 60, 120],
    "delta_skew": [0.0, 0.02, 0.05, 0.1, 0.2],
    "skew_cap": [2.0, 5.0, 10.0],
}
ENTERS = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
EXITS = [0.5, 1.0, 1.5, 2.0, 2.5]


def p_of(**kw):
    """Params dict holding only what differs from the default (so the default itself is {})."""
    return {k: v for k, v in kw.items() if DEFAULT[k] != v}


def main():
    variants = {name: [(v, p_of(**{name: v})) for v in vals] for name, vals in SWEEPS.items()}
    variants["enter/exit"] = [((e, x), p_of(enter=e, exit=x)) for e in ENTERS for x in EXITS if x < e]
    res = run_all([p for vs in variants.values() for _, p in vs])

    def tot(p, d):
        return res[(json.dumps(p, sort_keys=True), d)]["total"]

    base = {d: tot({}, d) for d in (-2, -1, 0)}
    print(f"Committed settings: {DEFAULT}\nBaseline per day: {base}\n")
    for name, vs in variants.items():
        cur = DEFAULT[name] if name in DEFAULT else (DEFAULT["enter"], DEFAULT["exit"])
        print(f"== {name} (committed: {cur})")
        print(f"   {'value':>12}" + "".join(f"{'day ' + str(d):>9}" for d in (-2, -1, 0)) + f"{'total':>10}")
        for v, p in vs:
            row = [tot(p, d) - base[d] for d in (-2, -1, 0)]
            mark = "  <- committed" if v == cur else ""
            print(f"   {str(v):>12}" + "".join(f"{x:>+9,}" for x in row) + f"{sum(row):>+10,}{mark}")
        held = []
        for t, tr in ROTATIONS.items():
            v, p = max(vs, key=lambda vp: sum(tot(vp[1], d) for d in tr))
            g = tot(p, t) - base[t]
            held.append(g)
            print(f"   rotation test {t:>2}: training picks {v} -> held-out change vs committed {g:+,}")
        print(f"   => held-out change if we let training pick: {sum(held):+,} over 3 rotations\n")


if __name__ == "__main__":
    buf = io.StringIO()
    with redirect_stdout(buf):
        main()
    text = buf.getvalue()
    print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "step1_vouchers_results.txt"), "w").write(text)

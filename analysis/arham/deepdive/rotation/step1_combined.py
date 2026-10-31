"""Step 1c: with the LYCHEE lean ON, (a) does the exposure-shading strength need retuning, and
(b) what does a BAD day look like at real (not idealised) scale?

(b) uses the "wrong-way" test: run the bot with the lean reversed (negative size). On a random
walk the lean and the reversed lean are equally likely to win, so the reversed lean's result on
our 3 days shows the size of the loss if LYCHEE moves AWAY from home as much as it moved toward it.
Writes step1_combined_results.txt next to this file.
"""
import io, json, os, sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from runner import run_all  # noqa: E402
from step1_lychee import ROTATIONS, fade, lychee_mean  # noqa: E402


def main():
    means = {d: lychee_mean(d) for d in (-2, -1, 0)}
    anchors = {t: (means[a] + means[b]) / 2 for t, (a, b) in ROTATIONS.items()}
    skews = [(s, c) for s in (0.03, 0.05, 0.08, 0.1) for c in (5.0, 10.0)]
    sizes = [100, 150, 200]

    def with_skew(p, s, c):
        q = dict(p)
        if s != 0.05:
            q["delta_skew"] = s
        if c != 5.0:
            q["skew_cap"] = c
        return q

    params = [{}]
    for t in ROTATIONS:
        params += [with_skew(fade(150, 60, anchors[t]), s, c) for s, c in skews]
        params += [fade(n, 60, anchors[t]) for n in sizes] + [fade(-n, 60, anchors[t]) for n in sizes]
    res = run_all(params)

    def tot(p, d):
        return res[(json.dumps(p, sort_keys=True), d)]["total"]

    base = {d: tot({}, d) for d in (-2, -1, 0)}
    print("a) Lean size 150, w=60: exposure-shading strength (delta_skew) and cap, held-out change vs no lean")
    print(f"{'skew':>6}{'cap':>6}" + "".join(f"{'test ' + str(t):>10}" for t in ROTATIONS) + f"{'sum':>10}")
    for s, c in skews:
        g = [tot(with_skew(fade(150, 60, anchors[t]), s, c), t) - base[t] for t in ROTATIONS]
        mark = "  <- current" if (s, c) == (0.05, 5.0) else ""
        print(f"{s:>6}{c:>6.0f}" + "".join(f"{x:>+10,}" for x in g) + f"{sum(g):>+10,}{mark}")

    print("\nb) Right-way lean vs WRONG-way lean (reversed sign) on each held-out day, w=60")
    print(f"{'size':>6}" + "".join(f"{'test ' + str(t):>18}" for t in ROTATIONS))
    for n in sizes:
        cells = []
        for t in ROTATIONS:
            good = tot(fade(n, 60, anchors[t]), t) - base[t]
            bad = tot(fade(-n, 60, anchors[t]), t) - base[t]
            cells.append(f"{good:+,} / {bad:+,}")
        print(f"{n:>6}" + "".join(f"{c:>18}" for c in cells))


if __name__ == "__main__":
    buf = io.StringIO()
    with redirect_stdout(buf):
        main()
    text = buf.getvalue()
    print(text)
    open(os.path.join(HERE, "step1_combined_results.txt"), "w").write(text)

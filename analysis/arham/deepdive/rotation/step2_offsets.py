"""Step 2: does a per-strike offset on top of the smile help on held-out days?

offsets_by_day.json (from offsets.py) holds each voucher's average gap from the smile on each day.
In each rotation the prior offset is the average over the TRAINING days only; the held-out day
scores it. Also tests learning the offsets live during the day (EMA), with and without the prior.
Writes step2_offsets_results.txt next to this file.
"""
import io, json, os, sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from runner import run_all  # noqa: E402

ROTATIONS = {-2: (-1, 0), -1: (-2, 0), 0: (-2, -1)}


def main():
    by_day = json.load(open(os.path.join(HERE, "offsets_by_day.json")))
    priors = {t: {s: round((by_day[str(a)][s] + by_day[str(b)][s]) / 2, 3) for s in by_day["0"]}
              for t, (a, b) in ROTATIONS.items()}
    per_rot = {  # name -> {test day: params}
        **{f"prior x{w}": {t: {"off_w": w, "off_prior": priors[t]} for t in ROTATIONS} for w in (0.5, 1.0, 1.5)},
        **{f"prior + live hl {h}": {t: {"off_w": 1.0, "off_prior": priors[t], "off_hl": h} for t in ROTATIONS}
           for h in (3000, 10000)},
        **{f"live only hl {h}": {t: {"off_w": 1.0, "off_hl": h} for t in ROTATIONS} for h in (1000, 3000, 10000)},
    }
    res = run_all([{}] + [p for v in per_rot.values() for p in v.values()])

    def tot(p, d):
        return res[(json.dumps(p, sort_keys=True), d)]["total"]

    base = {d: tot({}, d) for d in (-2, -1, 0)}
    print("Prior offsets (coins) used when testing each day = average of the other two days:")
    for t, pr in priors.items():
        print(f"  test {t:>2}: " + " ".join(f"{s[8:]}:{v:+.2f}" for s, v in pr.items()))
    print(f"\nChange vs committed bot on the HELD-OUT day (baseline {base})")
    print(f"{'variant':<24}" + "".join(f"{'test ' + str(t):>10}" for t in ROTATIONS) + f"{'sum':>10}")
    for name, v in per_rot.items():
        g = [tot(v[t], t) - base[t] for t in ROTATIONS]
        print(f"{name:<24}" + "".join(f"{x:>+10,}" for x in g) + f"{sum(g):>+10,}")


if __name__ == "__main__":
    buf = io.StringIO()
    with redirect_stdout(buf):
        main()
    text = buf.getvalue()
    print(text)
    open(os.path.join(HERE, "step2_offsets_results.txt"), "w").write(text)

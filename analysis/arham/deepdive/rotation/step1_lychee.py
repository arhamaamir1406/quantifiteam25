"""Step 1a: 3-way rotation test of the LYCHEE lean ("leash" bet through the vouchers).

For each rotation, the home price (fade_anchor) is the average LYCHEE price of the two TRAINING
days only, settings are picked on the training days, and the held-out day scores them.
Writes step1_lychee_results.txt next to this file.
"""
import csv, io, json, os, sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import REPO, run_all  # noqa: E402

ROTATIONS = {-2: (-1, 0), -1: (-2, 0), 0: (-2, -1)}  # test day: training days
NS = [50, 100, 150, 200, 250, 300]
WS = [40, 60, 90, 120]


def lychee_mean(day):
    xs = [float(r["mid_price"]) for r in csv.DictReader(open(os.path.join(REPO, "data", f"prices_day_{day}.csv")),
                                                        delimiter=";") if r["product"] == "LYCHEE"]
    return sum(xs) / len(xs)


def fade(n, w, anchor, hold=100000, lychee=1):
    return {"fade_n": n, "fade_w": w, "fade_anchor": round(anchor, 1), "fade_hold": hold, "fade_lychee": lychee}


def main():
    means = {d: lychee_mean(d) for d in (-2, -1, 0)}
    anchors = {t: (means[a] + means[b]) / 2 for t, (a, b) in ROTATIONS.items()}
    params = [{}]
    for t in ROTATIONS:
        params += [fade(n, w, anchors[t]) for n in NS for w in WS]
        params += [fade(150, 60, anchors[t], hold, ly) for hold in (0, 100000) for ly in (0, 1)]
    res = run_all(params)

    def tot(p, d):
        return res[(json.dumps(p, sort_keys=True), d)]["total"]

    base = {d: tot({}, d) for d in (-2, -1, 0)}

    def gain(p, d):
        return tot(p, d) - base[d]

    print("LYCHEE daily average price:", {d: round(m, 1) for d, m in means.items()})
    print("Home price used in each rotation (average of its 2 training days):",
          {f"test {t}": round(a, 1) for t, a in anchors.items()})
    print(f"Baseline (no lean) per day: {base}\n")

    print("A. Gain vs no lean on the HELD-OUT day, fade_w=60 (the candidate's width)")
    print(f"{'size':>6}" + "".join(f"{'test ' + str(t):>12}" for t in ROTATIONS) + f"{'sum':>10}{'worst':>9}")
    for n in NS:
        g = [gain(fade(n, 60, anchors[t]), t) for t in ROTATIONS]
        print(f"{n:>6}" + "".join(f"{v:>+12,}" for v in g) + f"{sum(g):>+10,}{min(g):>+9,}")

    print("\nB. Same, every width: held-out gain (sum over the 3 rotations) and how many of the 3 improved")
    print(f"{'size':>6}" + "".join(f"{'w=' + str(w):>16}" for w in WS))
    for n in NS:
        cells = []
        for w in WS:
            g = [gain(fade(n, w, anchors[t]), t) for t in ROTATIONS]
            cells.append(f"{sum(g):>+9,} ({sum(v > 0 for v in g)}/3)")
        print(f"{n:>6}" + "".join(f"{c:>16}" for c in cells))

    print("\nC. Honest pick: in each rotation, choose (size, width) by TRAINING days only, then score the held-out day")
    for t, tr in ROTATIONS.items():
        cands = [(n, w) for n in NS for w in WS]
        best = max(cands, key=lambda c: sum(gain(fade(*c, anchors[t]), d) for d in tr))
        trg = sum(gain(fade(*best, anchors[t]), d) for d in tr)
        print(f"  test day {t:>2}: training picks size {best[0]}, w={best[1]} (training gain {trg:+,}) "
              f"-> held-out gain {gain(fade(*best, anchors[t]), t):+,}; size 150/w60 would give "
              f"{gain(fade(150, 60, anchors[t]), t):+,}")

    print("\nD. Size 150, w=60: fixed home vs slowly updated home (hold), with/without centring LYCHEE quotes")
    for hold in (0, 100000):
        for ly in (0, 1):
            g = [gain(fade(150, 60, anchors[t], hold, ly), t) for t in ROTATIONS]
            print(f"  hold={hold:<6} lychee={ly}: held-out " + " ".join(f"{v:+,}" for v in g) + f"  sum {sum(g):+,}")


if __name__ == "__main__":
    buf = io.StringIO()
    with redirect_stdout(buf):
        main()
    text = buf.getvalue()
    print(text)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "step1_lychee_results.txt"), "w").write(text)

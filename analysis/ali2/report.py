"""Shared report: compare each variant of a product against Ali's original on every test group."""
import json
from runner import DAYS3, HALVES, SHIFT, STEP, MIRROR

GROUPS = [("3 days", DAYS3), ("6 halves", HALVES), ("mirrored", MIRROR), ("TOFFEE shifted", SHIFT),
          ("TOFFEE step", STEP)]


def table(product, res, keys=None, toffee=False):
    """One line per variant: PnL on the 3 days, then how many test days it beats Ali on per group."""
    ali = res["{}"]
    groups = [g for g in GROUPS if toffee or not g[0].startswith("TOFFEE")]
    lines = [f"\n=== {product}: Ali's original = {[ali[d] for d in DAYS3]} (sum {sum(ali[d] for d in DAYS3):,})",
             f"{'variant':<58}{'day -2':>8}{'day -1':>8}{'day 0':>8}{'3-day':>9}{'vs Ali':>8} | "
             + " ".join(f"{name:>14}" for name, _ in groups) + f"{'worst':>8}{'all-days +':>11}"]
    rows = []
    for k in (keys or res):
        r = res[k]
        three = [r[d] for d in DAYS3]
        wins, worst, alldiff = [], 0, 0
        for name, days in groups:
            diffs = [r[d] - ali[d] for d in days]
            wins.append(f"{sum(x > 0 for x in diffs)}/{len(days)} {sum(diffs) / 1000:+.1f}K")
            worst = min(worst, min(diffs))
            alldiff += sum(diffs)
        rows.append((alldiff, f"{k[:58]:<58}" + "".join(f"{x:>8,}" for x in three)
                     + f"{sum(three):>9,}{sum(three) - sum(ali[d] for d in DAYS3):>+8,} | "
                     + " ".join(f"{w:>14}" for w in wins) + f"{worst:>+8,}{alldiff:>+11,}"))
    rows.sort(key=lambda r: -r[0])
    return "\n".join(lines + [r for _, r in rows])

"""Compare each variant of a product against Sepehr's version on every test group."""
from runner import DAYS3, HALVES, PSHIFT, GSTEP, MIRROR
GROUPS = [("3 days", DAYS3), ("6 halves", HALVES), ("mirrored", MIRROR), ("PINK sum +-10", PSHIFT), ("GOLDEN step", GSTEP)]

def table(product, res, top=40):
    sep = res["{}"]
    groups = [(n, d) for n, d in GROUPS if all(x in sep for x in d)]
    lines = [f"\n=== {product}: Sepehr = {[sep[d] for d in DAYS3]} (sum {sum(sep[d] for d in DAYS3):,})",
             f"{'variant':<70}{'day -2':>8}{'day -1':>8}{'day 0':>8}{'3-day':>9}{'vs Sep':>8} | "
             + " ".join(f"{n:>15}" for n, _ in groups) + f"{'worst':>8}{'all +':>9}"]
    rows = []
    for k, r in res.items():
        three = [r[d] for d in DAYS3]; wins, worst, alld = [], 0, 0
        for n, days in groups:
            diffs = [r[d] - sep[d] for d in days]
            wins.append(f"{sum(x > 0 for x in diffs)}/{len(days)} {sum(diffs)/1000:+.1f}K")
            worst = min(worst, min(diffs)); alld += sum(diffs)
        rows.append((sum(three), f"{k[:70]:<70}" + "".join(f"{x:>8,}" for x in three) + f"{sum(three):>9,}{sum(three)-sum(sep[d] for d in DAYS3):>+8,} | "
                     + " ".join(f"{w:>15}" for w in wins) + f"{worst:>+8,}{alld:>+9,}"))
    rows.sort(key=lambda r: -r[0])
    return "\n".join(lines + [r for _, r in rows[:top]])

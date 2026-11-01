"""Check the hand-written final pearls.py gives exactly the lab's numbers for the chosen variants on
all 33 test days. Leaves strategies/pearls.py = the final file."""
import os, shutil, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import ALL, WRONG, PRODUCTS, WORK, evaluate, run_one, vkey, norm
DAYS = ALL + WRONG
FINAL = {
    "WHITE_PEARLS": {},
    "BLACK_PEARLS": {"kind": "join", "cap": 1},
    "GOLDEN_PEARLS": {"kind": "slide", "ride": 20, "guard": 3, "quiet": 6, "cap": 5, "slip": 0},
    "PINK_PEARLS": {"kind": "sum", "take": 1, "make": 1, "w": 0.5, "tgt_window": 5000},
    "BLUE_PEARLS": {"kind": "saw", "exit_take": 1, "n": 10, "trig": 12, "quiet": 10, "bounce": 10, "drift_pos": 20, "smin": 0.02},
}
if __name__ == "__main__":
    lab = evaluate({p: [{}, v] for p, v in FINAL.items()}, DAYS)
    shutil.copy(os.path.join(WORK, "final", "pearls.py"), os.path.join(WORK, "strategies", "pearls.py"))
    with ThreadPoolExecutor(14) as ex:
        real = dict(zip(DAYS, ex.map(lambda d: run_one({}, d), DAYS)))
    bad = 0
    for p in PRODUCTS:
        want = lab[p][vkey(norm(p, FINAL[p]))]
        for d in DAYS:
            if real[d][0][p] != want[d] or real[d][1]:
                bad += 1; print(f"MISMATCH {p} day {d}: final {real[d][0][p]} vs lab {want[d]} warning={real[d][1]}")
    print(f"mismatches: {bad} (of {len(PRODUCTS) * len(DAYS)})")
    tot = {d: sum(real[d][0].values()) for d in (1, 2, 3)}
    sep = {d: sum(lab[p]["{}"][d] for p in PRODUCTS) for d in (1, 2, 3)}
    print(f"Sepehr2 total days -2/-1/0: {list(tot.values())} = {sum(tot.values()):,}")
    print(f"Sepehr  total days -2/-1/0: {list(sep.values())} = {sum(sep.values()):,}")
    for p in PRODUCTS:
        print(f"  {p:<14} Sepehr2 {[real[d][0][p] for d in (1, 2, 3)]}  Sepehr {[lab[p]['{}'][d] for d in (1, 2, 3)]}")
    groups = {"6 half-days": [11, 12, 21, 22, 31, 32], "mirrored": [81, 82, 83], "PINK sum +-10": [41, 42, 43, 51, 52, 53],
              "GOLDEN steps +-100": [61, 62, 63, 71, 72, 73], "BLUE no sawtooth": [91, 92, 93], "PINK ignores sum": [94, 95, 96],
              "GOLDEN fake slide": [97, 98, 99]}
    for g, ds in groups.items():
        s2 = [sum(real[d][0].values()) for d in ds]; s1 = [sum(lab[p]["{}"][d] for p in PRODUCTS) for d in ds]
        print(f"  {g:<20} Sepehr2 {s2}  Sepehr {s1}  beats Sepehr on {sum(a > b for a, b in zip(s2, s1))}/{len(ds)}")

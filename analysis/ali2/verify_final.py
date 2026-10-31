"""Check the hand-written Ali2 core.py gives exactly the lab's numbers for the chosen variants,
on all 24 test days. Leaves strategies/core.py = the Ali2 file."""
import os, shutil, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runner import ALL, PRODUCTS, WORK, evaluate, run_one, vkey, norm  # noqa: E402  (copies core_lab in)

FINAL = {
    "AMETHYST": {"kind": "around", "take": 1, "make": 1},
    "TOFFEE_CAKE": {"mode": "hybrid", "win": 4000, "take": 10},
    "PAPER_LANTERNS": {"kind": "momo", "k": 0.75, "look": 100, "take": 1},
    "TELLURIUM": {"kind": "join", "cap": 6},
    "JELLY": {"cap": 3, "size": 2},
    "PEANUT_BUTTER": {"cap": 3, "size": 2, "edge": 4},
}

if __name__ == "__main__":
    lab = evaluate({p: [{}, v] for p, v in FINAL.items()})
    shutil.copy(os.path.join(WORK, "core_ali2.py"), os.path.join(WORK, "strategies", "core.py"))
    with ThreadPoolExecutor(14) as ex:
        real = dict(zip(ALL, ex.map(lambda d: run_one({}, d), ALL)))
    bad = 0
    for p in PRODUCTS:
        want = lab[p][vkey(norm(p, FINAL[p]))]
        for d in ALL:
            if real[d][0][p] != want[d] or real[d][1]:
                bad += 1
                print(f"MISMATCH {p} day {d}: core_ali2 {real[d][0][p]} vs lab {want[d]} warning={real[d][1]}")
    tot = {d: sum(real[d][0].values()) for d in (1, 2, 3)}
    ali = {d: sum(lab[p]["{}"][d] for p in PRODUCTS) for d in (1, 2, 3)}
    print(f"mismatches: {bad} (of {len(PRODUCTS) * len(ALL)})")
    print(f"Ali2 total on days -2/-1/0: {list(tot.values())} = {sum(tot.values()):,}")
    print(f"Ali  total on days -2/-1/0: {list(ali.values())} = {sum(ali.values()):,}")
    for p in PRODUCTS:
        print(f"  {p:<15} Ali2 {[real[d][0][p] for d in (1, 2, 3)]}  Ali {[lab[p]['{}'][d] for d in (1, 2, 3)]}")

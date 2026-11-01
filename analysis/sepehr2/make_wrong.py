"""'Wrong world' days: what if the scoring day does NOT have the pattern we trade?
  91-93  BLUE has no sawtooth: its mid follows WHITE's random walk, scaled to BLUE's tick size (1.42/2.27).
         BLUE keeps its own spread and book shape; each row (and that tick's trades) is shifted by an integer.
  94-96  PINK ignores the 50,000 sum: same trick, PINK's mid follows WHITE's walk scaled to PINK's tick size.
  97-99  GOLDEN fakes a slide: drops 50 at 2/tick at mid-day, then climbs back 50 straight away
         (PINK moves the other way so the sum holds).
"""
import json, os
from make_scenarios import read, write, shift_row, HALF
HERE = os.path.dirname(os.path.abspath(__file__))

def walk_shift(P, T, prod, scale):
    mids = {int(r["timestamp"]): float(r["mid_price"]) for r in P if r["product"] == prod}
    white = {int(r["timestamp"]): float(r["mid_price"]) for r in P if r["product"] == "WHITE_PEARLS"}
    t0 = min(mids)
    delta = {t: round(mids[t0] + scale * (white[t] - white[t0]) - mids[t]) for t in mids}
    P2 = [shift_row(r, delta[int(r["timestamp"])]) if r["product"] == prod else r for r in P]
    T2 = [{**r, "price": str(float(r["price"]) + delta[int(r["timestamp"])])} if r["symbol"] == prod else r for r in T]
    return P2, T2

def main():
    m = json.load(open(os.path.join(HERE, "scenarios.json")))
    for n, day in enumerate((-2, -1, 0), 1):
        P, T = read(day)
        write(90 + n, *walk_shift(P, T, "BLUE_PEARLS", 1.42 / 2.27)); m[str(90 + n)] = f"day {day} BLUE random walk (no sawtooth)"
        write(93 + n, *walk_shift(P, T, "PINK_PEARLS", 1.0 / 2.27)); m[str(93 + n)] = f"day {day} PINK random walk (ignores sum)"
        def amt(t, prod):
            t = int(t); s = 0
            if HALF <= t < HALF + 2500: s = -min(50, 2 * ((t - HALF) // 100 + 1))
            elif HALF + 2500 <= t < HALF + 5000: s = -50 + min(50, 2 * ((t - HALF - 2500) // 100 + 1))
            return s if prod == "GOLDEN_PEARLS" else (-s if prod == "PINK_PEARLS" else 0)
        write(96 + n, [shift_row(r, amt(r["timestamp"], r["product"])) for r in P],
              [{**r, "price": str(float(r["price"]) + amt(r["timestamp"], r["symbol"]))} for r in T])
        m[str(96 + n)] = f"day {day} GOLDEN fake slide (-50 then back)"
    json.dump(m, open(os.path.join(HERE, "scenarios.json"), "w"), indent=1); print(len(m), "scenario days")

if __name__ == "__main__": main()

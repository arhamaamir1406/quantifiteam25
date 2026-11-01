"""Stress-test days for the pearls (written into ../data as extra day numbers).
  1,2,3          days -2/-1/0, pearls only
  11..32         each day split in half (6 half-days, each starts flat)
  41-43 / 51-53  PINK shifted +10 / -10 all day (the five-pearl sum sits at 50,010 / 49,990, not 50,000)
  61-63 / 71-73  GOLDEN steps -100 / +100 halfway through the day (sliding 2 per tick, like the real
                 steps), with PINK moving the opposite way so the sum still holds
  81-83          every pearl mirrored around its day -2 open (15000/12000/8000/10000/5000, sum 50,000)
"""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "..", "data")
PEARLS = ["WHITE_PEARLS", "BLACK_PEARLS", "GOLDEN_PEARLS", "PINK_PEARLS", "BLUE_PEARLS"]
CENTER = {"WHITE_PEARLS": 15000, "BLACK_PEARLS": 12000, "GOLDEN_PEARLS": 8000, "PINK_PEARLS": 10000, "BLUE_PEARLS": 5000}
HALF = 500_000

def read(day):
    with open(os.path.join(DATA, f"prices_day_{day}.csv"), newline="") as f: prices = list(csv.DictReader(f, delimiter=";"))
    with open(os.path.join(DATA, f"trades_day_{day}.csv"), newline="") as f: trades = list(csv.DictReader(f, delimiter=";"))
    return [r for r in prices if r["product"] in PEARLS], [r for r in trades if r["symbol"] in PEARLS]

def write(nd, prices, trades):
    with open(os.path.join(DATA, f"prices_day_{nd}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(prices[0].keys()), delimiter=";"); w.writeheader()
        for r in prices: w.writerow({**r, "day": nd})
    with open(os.path.join(DATA, f"trades_day_{nd}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"], delimiter=";"); w.writeheader(); w.writerows(trades)

def shift_row(r, k):
    r = dict(r)
    if k == 0: return r
    for s in ("bid", "ask"):
        for i in (1, 2, 3):
            if r[f"{s}_price_{i}"]: r[f"{s}_price_{i}"] = str(int(float(r[f"{s}_price_{i}"])) + k)
    r["mid_price"] = str(float(r["mid_price"]) + k); return r

def mirror_row(r, c):
    out = dict(r)
    for i in (1, 2, 3):
        for new, old in (("bid", "ask"), ("ask", "bid")):
            p, v = r[f"{old}_price_{i}"], r[f"{old}_volume_{i}"]
            out[f"{new}_price_{i}"] = str(2 * c - int(float(p))) if p else ""; out[f"{new}_volume_{i}"] = v
    out["mid_price"] = str(2 * c - float(r["mid_price"])); return out

def main():
    m = {}
    for n, day in enumerate((-2, -1, 0), 1):
        P, T = read(day)
        write(n, P, T); m[n] = f"day {day}"
        write(n*10+1, [r for r in P if int(r["timestamp"]) < HALF], [r for r in T if int(r["timestamp"]) < HALF])
        write(n*10+2, [r for r in P if int(r["timestamp"]) >= HALF], [r for r in T if int(r["timestamp"]) >= HALF])
        m[n*10+1], m[n*10+2] = f"day {day} 1st half", f"day {day} 2nd half"
        for base, k in ((40, 10), (50, -10)):
            sh = lambda prod: k if prod == "PINK_PEARLS" else 0
            write(base+n, [shift_row(r, sh(r["product"])) for r in P], [{**r, "price": str(float(r["price"]) + sh(r["symbol"]))} for r in T])
            m[base+n] = f"day {day} PINK shifted {k:+}"
        for base, k in ((60, -100), (70, 100)):
            def amt(t, prod):
                t = int(t); s = 0 if t < HALF else min(abs(k), 2 * ((t - HALF) // 100 + 1))
                s = s if k > 0 else -s
                return s if prod == "GOLDEN_PEARLS" else (-s if prod == "PINK_PEARLS" else 0)
            write(base+n, [shift_row(r, amt(r["timestamp"], r["product"])) for r in P],
                  [{**r, "price": str(float(r["price"]) + amt(r["timestamp"], r["symbol"]))} for r in T])
            m[base+n] = f"day {day} GOLDEN steps {k:+} mid-day"
        write(80+n, [mirror_row(r, CENTER[r["product"]]) for r in P], [{**r, "price": str(2*CENTER[r["symbol"]] - float(r["price"]))} for r in T])
        m[80+n] = f"day {day} mirrored"
    json.dump(m, open(os.path.join(HERE, "scenarios.json"), "w"), indent=1); print(len(m), "scenario days")

if __name__ == "__main__": main()

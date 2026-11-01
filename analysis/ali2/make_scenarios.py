"""Make the stress-test "days" for Ali's products (written into ../data as extra day numbers).

  1, 2, 3       days -2, -1, 0 with only Ali's 6 products (faster to run)
  11,12 21,22 31,32   each day split into its first and second half (6 half-days)
  41-43 / 51-53       TOFFEE_CAKE's whole day shifted +25 / -25 (the scoring day sits at a different level)
  61-63 / 71-73       TOFFEE_CAKE's second half shifted +30 / -30 (the level jumps mid-day)
  81-83               every product mirrored upside down (uptrends become downtrends; AMETHYST
                      mirrored around 10000 and TOFFEE around 5000 so their homes stay put)
"""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
ALI = ["AMETHYST", "TOFFEE_CAKE", "PAPER_LANTERNS", "TELLURIUM", "JELLY", "PEANUT_BUTTER"]
HALF = 500_000


def read(day):
    with open(os.path.join(DATA, f"prices_day_{day}.csv"), newline="") as f:
        prices = [r for r in csv.DictReader(f, delimiter=";")]
    with open(os.path.join(DATA, f"trades_day_{day}.csv"), newline="") as f:
        trades = [r for r in csv.DictReader(f, delimiter=";")]
    return prices, trades


def write(new_day, prices, trades):
    pf, tf = list(prices[0].keys()), ["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]
    with open(os.path.join(DATA, f"prices_day_{new_day}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, pf, delimiter=";")
        w.writeheader()
        for r in prices:
            w.writerow({**r, "day": new_day})
    with open(os.path.join(DATA, f"trades_day_{new_day}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, tf, delimiter=";")
        w.writeheader()
        w.writerows(trades)


def shift_row(r, k):
    r = dict(r)
    for side in ("bid", "ask"):
        for i in (1, 2, 3):
            if r[f"{side}_price_{i}"]:
                r[f"{side}_price_{i}"] = str(int(float(r[f"{side}_price_{i}"])) + k)
    r["mid_price"] = str(float(r["mid_price"]) + k)
    return r


def mirror_row(r, c):
    out = dict(r)
    for i in (1, 2, 3):  # new bids = mirrored old asks and vice versa
        for new, old in (("bid", "ask"), ("ask", "bid")):
            p, v = r[f"{old}_price_{i}"], r[f"{old}_volume_{i}"]
            out[f"{new}_price_{i}"] = str(2 * c - int(float(p))) if p else ""
            out[f"{new}_volume_{i}"] = v
    out["mid_price"] = str(2 * c - float(r["mid_price"]))
    return out


def main():
    mapping = {}
    for n, day in enumerate((-2, -1, 0), 1):
        prices, trades = read(day)
        P = [r for r in prices if r["product"] in ALI]
        T = [r for r in trades if r["symbol"] in ALI]
        write(n, P, T); mapping[n] = f"day {day}"
        write(n * 10 + 1, [r for r in P if int(r["timestamp"]) < HALF], [r for r in T if int(r["timestamp"]) < HALF])
        write(n * 10 + 2, [r for r in P if int(r["timestamp"]) >= HALF], [r for r in T if int(r["timestamp"]) >= HALF])
        mapping[n * 10 + 1], mapping[n * 10 + 2] = f"day {day} 1st half", f"day {day} 2nd half"
        TP = [r for r in P if r["product"] == "TOFFEE_CAKE"]
        TT = [r for r in T if r["symbol"] == "TOFFEE_CAKE"]
        for base, k, step in ((40, 25, False), (50, -25, False), (60, 30, True), (70, -30, True)):
            kk = lambda t: k if (not step or int(t) >= HALF) else 0
            write(base + n, [shift_row(r, kk(r["timestamp"])) for r in TP],
                  [{**r, "price": str(float(r["price"]) + kk(r["timestamp"]))} for r in TT])
            mapping[base + n] = f"day {day} TOFFEE {'2nd half ' if step else ''}shifted {k:+}"
        centers = {"AMETHYST": 10000, "TOFFEE_CAKE": 5000}
        for r in P:
            centers.setdefault(r["product"], round(float(r["mid_price"])))
        write(80 + n, [mirror_row(r, centers[r["product"]]) for r in P],
              [{**r, "price": str(2 * centers[r["symbol"]] - float(r["price"]))} for r in T])
        mapping[80 + n] = f"day {day} mirrored"
    json.dump(mapping, open(os.path.join(HERE, "scenarios.json"), "w"), indent=1)
    print(mapping)


if __name__ == "__main__":
    main()

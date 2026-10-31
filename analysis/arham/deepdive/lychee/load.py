import csv, statistics as st
from collections import defaultdict
DATA = r"C:/Users/arham/YEAR2/utefa/quantifi/data"
def load():
    mids = defaultdict(lambda: defaultdict(dict)); book = defaultdict(lambda: defaultdict(dict)); trades = defaultdict(lambda: defaultdict(list))
    for d in (-2, -1, 0):
        for r in csv.DictReader(open(f"{DATA}/prices_day_{d}.csv"), delimiter=";"):
            t = int(r["timestamp"]); p = r["product"]
            bids = [(float(r[f"bid_price_{i}"]), int(float(r[f"bid_volume_{i}"]))) for i in (1,2,3) if r[f"bid_price_{i}"]]
            asks = [(float(r[f"ask_price_{i}"]), int(float(r[f"ask_volume_{i}"]))) for i in (1,2,3) if r[f"ask_price_{i}"]]
            book[d][p][t] = (bids, asks)
            if r["mid_price"]: mids[d][p][t] = float(r["mid_price"])
        for r in csv.DictReader(open(f"{DATA}/trades_day_{d}.csv"), delimiter=";"):
            trades[d][r["symbol"]].append((int(r["timestamp"]), float(r["price"]), int(float(r["quantity"]))))
    return mids, book, trades

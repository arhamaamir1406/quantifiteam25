"""Local copy of UTEFA's backtester: replays the CSVs tick by tick, calls Trader.run(),
decides which orders fill, and reports profit (PnL) per product per day.

Usage:
    python backtest.py                          # whole team bot (trader.py), days -2 -1 0
    python backtest.py --only fruit_lychee      # just one strategy (core / fruit_lychee / pearls)
    python backtest.py --days -2 -1             # tune on these two days...
    python backtest.py --days 0                 # ...then check on day 0 as a fake "unseen" day
    python backtest.py --file Team07QuantiFi2026.py   # any single-file trader (e.g. the built submission)
    python backtest.py --log results/run.csv    # per-tick position + PnL for plotting

Fill rules (from the QuantiFi wiki; anything marked ASSUMPTION is our guess and should be
checked by running the same trader here and on utefa.com and comparing the PnL):
  1. Position limits: if all of a product's buys (or all its sells) filling would break its
     limit, every order for that product is cancelled that tick.
     ASSUMPTION: same rule as IMC Prosperity; trader.py clips orders so this never triggers.
  2. Taking: a buy at or above a resting ask trades immediately at the ask's price, best
     price first, up to the volume shown (mirror image for sells).
  3. Waiting (passive) fill: whatever is left fills against the historical trades of the
     SAME tick if the trade price is equal or better for you (buy: trade price <= your price;
     sell: trade price >= your price). You get YOUR price.
     ASSUMPTION: capped at each trade's quantity, and a trade can only be used once.
  4. Orders don't carry over: anything unfilled is cancelled at the end of the tick.
  5. The bot sees market trades from the PREVIOUS tick only (no peeking at the trades that
     will decide its own fills).
  6. Each day runs on its own (start flat, 0 cash). PnL = cash + position x final mid price.
"""
import argparse
import csv
import importlib.util
import io
import os
import sys
import time
from collections import defaultdict
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from datamodel import Listing, Observation, Order, OrderDepth, Trade, TradingState  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data")
DAYS = [-2, -1, 0]

# Position limits from the wiki's Products tab (used for --file traders and rule 1)
LIMITS = {
    "AMETHYST": 50, "TOFFEE_CAKE": 50, "PAPER_LANTERNS": 50, "TELLURIUM": 40,
    "JELLY": 50, "PEANUT_BUTTER": 50, "DRAGONFRUIT": 40, "GRANADILLA": 40,
    "MANGOSTEEN": 40, "FRUIT_BASKET": 40, "LYCHEE": 200,
    "WHITE_PEARLS": 20, "BLACK_PEARLS": 20, "GOLDEN_PEARLS": 20,
    "PINK_PEARLS": 20, "BLUE_PEARLS": 20,
    **{f"VOUCHER_{k}": 50 for k in (6800, 7000, 7200, 7300, 7400, 7500, 7600, 7750, 7900, 8100)},
}


# ----------------------------------------------------------------------------- loading
def load_day(day):
    """Returns (books, mids, trades):
    books[t][product]  = (bids {price: vol}, asks {price: -vol})
    mids[t][product]   = mid price
    trades[t][product] = [(price, qty), ...]
    """
    books, mids = defaultdict(dict), defaultdict(dict)
    with open(os.path.join(DATA_DIR, f"prices_day_{day}.csv"), newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            t, p = int(r["timestamp"]), r["product"]
            bids, asks = {}, {}
            for i in (1, 2, 3):
                if r[f"bid_price_{i}"]:
                    bids[int(float(r[f"bid_price_{i}"]))] = int(float(r[f"bid_volume_{i}"]))
                if r[f"ask_price_{i}"]:
                    asks[int(float(r[f"ask_price_{i}"]))] = -int(float(r[f"ask_volume_{i}"]))
            books[t][p] = (bids, asks)
            mids[t][p] = float(r["mid_price"])
    trades = defaultdict(lambda: defaultdict(list))
    with open(os.path.join(DATA_DIR, f"trades_day_{day}.csv"), newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            trades[int(r["timestamp"])][r["symbol"]].append(
                (int(float(r["price"])), int(float(r["quantity"])))
            )
    return books, mids, trades


def load_trader(path, only):
    if path is None:
        from trader import Trader
        return Trader(only=only) if only else Trader()
    spec = importlib.util.spec_from_file_location("submitted_trader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Trader()


# ----------------------------------------------------------------------------- matching
def execute(order, bids, asks, tick_trades, fills):
    """Fill one order against the book (taking) then against this tick's trades
    (waiting). Mutates bids/asks/tick_trades so volume can't be used twice."""
    qty = order.quantity
    if qty > 0:
        for price in sorted(asks):
            if price > order.price or qty == 0:
                break
            n = min(qty, -asks[price])
            asks[price] += n
            if asks[price] == 0:
                del asks[price]
            fills.append((price, n))
            qty -= n
        for tr in tick_trades:
            if qty == 0:
                break
            if tr[1] > 0 and tr[0] <= order.price:
                n = min(qty, tr[1])
                tr[1] -= n
                fills.append((order.price, n))
                qty -= n
    elif qty < 0:
        qty = -qty
        for price in sorted(bids, reverse=True):
            if price < order.price or qty == 0:
                break
            n = min(qty, bids[price])
            bids[price] -= n
            if bids[price] == 0:
                del bids[price]
            fills.append((price, -n))
            qty -= n
        for tr in tick_trades:
            if qty == 0:
                break
            if tr[1] > 0 and tr[0] >= order.price:
                n = min(qty, tr[1])
                tr[1] -= n
                fills.append((order.price, -n))
                qty -= n


def run_day(trader, day, log_writer=None, quiet=True):
    books, mids, trades = load_day(day)
    timestamps = sorted(books)
    products = sorted(books[timestamps[0]])
    listings = {p: Listing(p, p, "COINS") for p in products}

    position = defaultdict(int)
    cash = defaultdict(float)
    trader_data = ""
    prev_market, prev_own = {}, {}
    stats = {"crashes": 0, "limit_cancels": 0}

    for t in timestamps:
        depths = {}
        for p, (bids, asks) in books[t].items():
            depths[p] = OrderDepth(dict(bids), dict(asks))
        state = TradingState(
            trader_data, t, listings, depths, prev_own, prev_market,
            dict(position), Observation({}, {}),
        )
        buf = io.StringIO()
        try:
            if quiet:  # hide the bot's print() spam, but still notice strategy crashes below
                with redirect_stdout(buf):
                    orders, _, trader_data = trader.run(state)
            else:
                orders, _, trader_data = trader.run(state)
        except Exception as e:  # UTEFA skips ticks where the bot crashes
            stats["crashes"] += 1
            if stats["crashes"] <= 3:
                print(f"  day {day} t={t}: run() crashed: {e!r}")
            orders = {}
        for line in buf.getvalue().splitlines():
            if "crashed" in line:  # trader.py caught a strategy crash and printed it
                stats["crashes"] += 1
                if stats["crashes"] <= 3:
                    print(f"  day {day}: {line}")
        if not isinstance(trader_data, str):
            trader_data = ""

        own = defaultdict(list)
        tick_trades = {p: [[pr, q] for pr, q in lst] for p, lst in trades.get(t, {}).items()}
        for product, order_list in (orders or {}).items():
            if product not in books[t] or not order_list:
                continue
            limit = LIMITS.get(product, 0)
            buys = sum(o.quantity for o in order_list if o.quantity > 0)
            sells = -sum(o.quantity for o in order_list if o.quantity < 0)
            if position[product] + buys > limit or position[product] - sells < -limit:
                stats["limit_cancels"] += 1
                continue
            bids, asks = dict(books[t][product][0]), dict(books[t][product][1])
            for o in order_list:
                fills = []
                execute(o, bids, asks, tick_trades.get(product, []), fills)
                for price, n in fills:
                    position[product] += n
                    cash[product] -= price * n
                    own[product].append(
                        Trade(product, price, abs(n),
                              "SUBMISSION" if n > 0 else None,
                              "SUBMISSION" if n < 0 else None, t)
                    )

        if log_writer is not None:
            for p in set(position) | set(cash):
                log_writer.writerow([day, t, p, position[p], round(cash[p] + position[p] * mids[t][p], 1)])

        prev_own = dict(own)
        prev_market = {
            p: [Trade(p, pr, q, None, None, t) for pr, q in lst]
            for p, lst in trades.get(t, {}).items()
        }

    last = timestamps[-1]
    pnl = {p: cash[p] + position[p] * mids[last][p] for p in products}
    return pnl, dict(position), stats


# ----------------------------------------------------------------------------- report
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", help="strategy names from trader.py (core, fruit_lychee, pearls)")
    ap.add_argument("--days", nargs="+", type=int, default=DAYS)
    ap.add_argument("--file", help="backtest this single-file trader instead of trader.py")
    ap.add_argument("--log", help="write per-tick position/PnL to this CSV")
    ap.add_argument("--verbose", action="store_true", help="show the bot's print() output")
    args = ap.parse_args()

    trader = load_trader(args.file, args.only)
    owner = {}
    if args.file is None:
        for name, strat in trader.strategies.items():
            for p in strat.LIMITS:
                owner[p] = name

    log_file = log_writer = None
    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
        log_file = open(args.log, "w", newline="")
        log_writer = csv.writer(log_file, delimiter=";")
        log_writer.writerow(["day", "timestamp", "product", "position", "pnl"])

    label = args.file or ("trader.py" + (f" --only {' '.join(args.only)}" if args.only else ""))
    print(f"Backtesting {label} on days {' '.join(map(str, args.days))}")
    results, totals_stats = {}, {"crashes": 0, "limit_cancels": 0}
    for day in args.days:
        start = time.time()
        # A fresh Trader per day, like a fresh run on UTEFA's site
        trader = load_trader(args.file, args.only)
        pnl, pos, stats = run_day(trader, day, log_writer, quiet=not args.verbose)
        results[day] = pnl
        for k in totals_stats:
            totals_stats[k] += stats[k]
        print(f"  day {day:>2} done in {time.time() - start:.1f}s")
    if log_file:
        log_file.close()

    products = sorted(set().union(*(r.keys() for r in results.values())))
    traded = [p for p in products if any(abs(results[d].get(p, 0)) > 1e-9 for d in args.days)]
    groups = defaultdict(list)
    for p in traded:
        groups[owner.get(p, "")].append(p)

    w = 11
    header = f"{'product':<16}" + "".join(f"{'day ' + str(d):>{w}}" for d in args.days) + f"{'total':>{w}}"
    print("\n" + header)
    print("-" * len(header))
    grand = defaultdict(float)
    for group in sorted(groups):
        if group:
            print(f"[{group}]")
        sub = defaultdict(float)
        for p in groups[group]:
            row = [results[d].get(p, 0) for d in args.days]
            for d, v in zip(args.days, row):
                sub[d] += v
                grand[d] += v
            print(f"{p:<16}" + "".join(f"{v:>{w},.0f}" for v in row) + f"{sum(row):>{w},.0f}")
        if group and len(groups) > 1:
            row = [sub[d] for d in args.days]
            print(f"{'  subtotal':<16}" + "".join(f"{v:>{w},.0f}" for v in row) + f"{sum(row):>{w},.0f}")
    print("-" * len(header))
    row = [grand[d] for d in args.days]
    print(f"{'TOTAL':<16}" + "".join(f"{v:>{w},.0f}" for v in row) + f"{sum(row):>{w},.0f}")
    if totals_stats["crashes"] or totals_stats["limit_cancels"]:
        print(f"\nWARNING: {totals_stats['crashes']} crashed ticks, "
              f"{totals_stats['limit_cancels']} product-ticks cancelled for breaking position limits")


if __name__ == "__main__":
    main()

"""Safety test of the BUILT submission file (Team25QuantiFi2026.py):
  1. Fuzz: 3,000 ticks of day 0 with random damage: one side of a book missing, products
     missing, no market trades, positions at or near the limits. Any crash or any order that
     could break a limit (or has a non-integer price/quantity) is reported.
  2. Speed and memory on a normal full day: time per run() call and traderData size.
"""
import importlib.util, io, os, random, sys, time
from contextlib import redirect_stdout

WORK = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, WORK)
from backtest import LIMITS, load_day  # noqa: E402
from datamodel import Listing, Observation, OrderDepth, Trade, TradingState  # noqa: E402

spec = importlib.util.spec_from_file_location("sub", os.path.join(WORK, "Team25QuantiFi2026.py"))
sub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sub)


def state_at(t, books, trades, trader_data, position, damage, rng):
    depths, market = {}, {}
    for p, (bids, asks) in books[t].items():
        if damage and rng.random() < 0.05:
            continue  # product missing this tick
        b, a = dict(bids), dict(asks)
        if damage and rng.random() < 0.08:
            b = {}
        if damage and rng.random() < 0.08:
            a = {}
        depths[p] = OrderDepth(b, a)
    if not (damage and rng.random() < 0.3):
        market = {p: [Trade(p, pr, q, None, None, t) for pr, q in lst] for p, lst in trades.get(t - 100, {}).items()}
    listings = {p: Listing(p, p, "COINS") for p in books[t]}
    return TradingState(trader_data, t, listings, depths, {}, market, position, Observation({}, {}))


def main():
    books, mids, trades = load_day(0)
    ts = sorted(books)
    rng = random.Random(1)

    # 1. fuzz
    trader, td, problems, crashes = sub.Trader(), "", 0, 0
    for t in ts[:3000]:
        position = {p: rng.choice([0, LIMITS[p], -LIMITS[p], rng.randint(-LIMITS[p], LIMITS[p])])
                    for p in LIMITS if rng.random() < 0.7}
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                orders, conv, td = trader.run(state_at(t, books, trades, td, position, True, rng))
        except Exception as e:
            crashes += 1
            print(f"run() itself crashed at t={t}: {e!r}")
            continue
        if "crashed" in buf.getvalue():
            crashes += 1
            if crashes <= 5:
                print(buf.getvalue().strip())
        for p, os_ in orders.items():
            pos = position.get(p, 0)
            buys = sum(o.quantity for o in os_ if o.quantity > 0)
            sells = -sum(o.quantity for o in os_ if o.quantity < 0)
            ok = (pos + buys <= LIMITS[p] and pos - sells >= -LIMITS[p]
                  and all(isinstance(o.price, int) and isinstance(o.quantity, int) and o.quantity != 0 for o in os_))
            if not ok:
                problems += 1
                if problems <= 5:
                    print(f"BAD ORDERS t={t} {p} pos={pos}: {[(o.price, o.quantity) for o in os_]}")
    print(f"fuzz: 3000 damaged ticks, {crashes} strategy crashes, {problems} bad order lists")

    # 2. speed + traderData size on a normal day (positions from a real backtest are not needed
    #    for timing; we feed position 0)
    trader, td, times, sizes = sub.Trader(), "", [], []
    for t in ts:
        st = state_at(t, books, trades, td, {}, False, rng)
        t0 = time.perf_counter()
        with redirect_stdout(io.StringIO()):
            orders, conv, td = trader.run(st)
        times.append(time.perf_counter() - t0)
        sizes.append(len(td))
    times.sort()
    print(f"speed: mean {1000 * sum(times) / len(times):.2f} ms, 99th pct {1000 * times[int(.99 * len(times))]:.2f} ms, "
          f"max {1000 * times[-1]:.2f} ms per tick")
    print(f"traderData: max {max(sizes):,} characters")


if __name__ == "__main__":
    main()

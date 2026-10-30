"""Re-creates every number and chart in NOTES.md (for the abstract).

    pip install pandas matplotlib        # analysis only; the bot itself stays plain Python
    python analysis/arham/make_plots.py  # ~1 minute, writes analysis/arham/plots/*.png

It runs the real bot (strategies/fruit_lychee.py) through backtest.py with its debug hook on,
so the fair values in the charts are exactly the ones the bot traded on.
"""
import csv
import io
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import backtest  # noqa: E402
from style import AQUA, BLUE, INK2, MUTED, ORANGE, plt, thousands  # noqa: E402
from trader import Trader  # noqa: E402

OUT = os.path.join(HERE, "plots")
DAYS = [-2, -1, 0]
FRUITS = ["DRAGONFRUIT", "GRANADILLA", "MANGOSTEEN"]


def run_bot():
    """Run the fruit_lychee strategy on each day; keep its debug records and per-tick PnL."""
    runs = {}
    for day in DAYS:
        trader = Trader(only=["fruit_lychee"])
        strat = trader.strategies["fruit_lychee"]
        strat.debug = []
        buf = io.StringIO()
        pnl, _, stats = backtest.run_day(trader, day, csv.writer(buf, delimiter=";"))
        log = pd.read_csv(io.StringIO(buf.getvalue()), sep=";", header=None,
                          names=["day", "timestamp", "product", "position", "pnl"])
        runs[day] = {"pnl": pnl, "debug": strat.debug, "log": log, "strat": strat, "stats": stats}
        print(f"day {day}: bot PnL {sum(v for p, v in pnl.items() if p in strat.LIMITS):,.0f}")
    return runs


def load_prices():
    frames = [pd.read_csv(os.path.join(ROOT, "data", f"prices_day_{d}.csv"), sep=";") for d in DAYS]
    return pd.concat(frames, ignore_index=True)


def load_trades():
    frames = []
    for d in DAYS:
        t = pd.read_csv(os.path.join(ROOT, "data", f"trades_day_{d}.csv"), sep=";")
        t["day"] = d
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


def smile_vol(c, x):
    return c[0] + c[1] * x + c[2] * x * x


# ----------------------------------------------------------------------------- charts
def chart_smile(runs):
    """Implied vol of every voucher vs moneyness on day 0: one smooth smile."""
    strat, dbg = runs[0]["strat"], runs[0]["debug"]
    T0 = strat.p["days_to_expiry"]
    xs, ys = [], []
    for rec in dbg[::20]:
        T = T0 - rec["t"] / 1e6
        for sym, m in rec["mid"].items():
            iv = strat.implied_vol(m, rec["S"], strat.VOUCHERS[sym], T, smile_vol(rec["smile"], rec["x"][sym]))
            if iv is not None:
                xs.append(rec["x"][sym])
                ys.append(iv * 100)
    coef = np.mean([rec["smile"] for rec in dbg[len(dbg) // 4:]], axis=0)
    grid = np.linspace(min(xs), max(xs), 200)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.scatter(xs, ys, s=4, color=MUTED, alpha=0.25, linewidths=0)
    ax.scatter([], [], s=16, color=MUTED, label="each voucher's implied vol, every 20 ticks")
    ax.plot(grid, smile_vol(coef, grid) * 100, color=BLUE, label="fitted smile (bot's average)")
    for sym, K in strat.VOUCHERS.items():
        xk = np.mean([rec["x"][sym] for rec in dbg[::200] if sym in rec["x"]])
        ax.annotate(str(K), (xk, max(ys) + 0.05), ha="center", fontsize=8, color=INK2, annotation_clip=False)
    ax.set_xlabel("moneyness  100 x ln(strike / LYCHEE) / sqrt(days left)")
    ax.set_ylabel("implied vol (% per sqrt day)")
    ax.set_title("Day 0: all ten vouchers sit on one smile (strike labels on top)", pad=18)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "smile.png"))
    plt.close(fig)


def chart_reversion(runs, sym="VOUCHER_7500", day=-1, start=300_000, end=500_000):
    """Price vs fair value for one voucher, the gap, and what the bot held."""
    dbg = [r for r in runs[day]["debug"] if start <= r["t"] <= end and sym in r["fair"]]
    t = np.array([r["t"] for r in dbg]) / 100
    mid = np.array([r["mid"][sym] for r in dbg])
    fair = np.array([r["fair"][sym] for r in dbg])
    log = runs[day]["log"]
    pos = log[(log["product"] == sym) & log.timestamp.between(start, end)].set_index("timestamp").position
    p = runs[day]["strat"].p
    fig, axs = plt.subplots(3, 1, figsize=(8, 6.5), sharex=True, gridspec_kw={"height_ratios": [2, 1.3, 1]})
    axs[0].plot(t, mid, color=MUTED, lw=1.2, label="market mid price")
    axs[0].plot(t, fair, color=BLUE, label="bot's fair value")
    axs[0].set_ylabel("price")
    axs[0].legend(loc="upper left", ncol=2)
    axs[0].set_title(f"{sym}, day {day}: the price keeps snapping back to fair value")
    gap = mid - fair
    axs[1].plot(t, gap, color=BLUE, lw=1.2)
    for y, txt, va in ((p["enter"] + 1.5, "sell zone", "bottom"), (-(p["enter"] + 1.5), "buy zone", "top")):
        axs[1].axhline(y, color=ORANGE, lw=1)
        axs[1].annotate(txt, (t[0], y), xytext=(2, 2 if va == "bottom" else -2), textcoords="offset points",
                        va=va, fontsize=8, color=INK2)
    axs[1].axhline(0, color=MUTED, lw=0.8)
    axs[1].set_ylabel("price - fair")
    axs[2].step(pos.index / 100, pos.values, where="post", color=BLUE)
    axs[2].set_ylabel("our position")
    axs[2].set_yticks([-50, 0, 50])
    axs[2].set_xlabel("tick")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "reversion_example.png"))
    plt.close(fig)


def chart_trade_side(runs, trades):
    """What fraction of market trades are buys, by how far the price was from the smile."""
    rows = []
    for day in DAYS:
        strat = runs[day]["strat"]
        by_t = {r["t"]: r for r in runs[day]["debug"]}
        T0 = strat.p["days_to_expiry"]
        tr = trades[(trades.day == day) & trades.symbol.str.startswith("VOUCHER")]
        for _, row in tr.iterrows():
            rec = by_t.get(row.timestamp)
            if rec is None or row.symbol not in rec["mid"] or rec["t"] < 50_000:
                continue
            K = strat.VOUCHERS[row.symbol]
            fair = strat.bs_call(rec["S"], K, T0 - rec["t"] / 1e6, smile_vol(rec["smile"], rec["x"][row.symbol]))
            gap = rec["mid"][row.symbol] - fair
            rows.append((gap, 1 if row.price > rec["mid"][row.symbol] else 0))
    df = pd.DataFrame(rows, columns=["gap", "buy"])
    edges = [-np.inf, -8, -5, -3, -1, 1, 3, 5, 8, np.inf]
    labels = ["< -8", "-8..-5", "-5..-3", "-3..-1", "-1..1", "1..3", "3..5", "5..8", "> 8"]
    df["bin"] = pd.cut(df.gap, edges, labels=labels)
    share = df.groupby("bin", observed=False).buy.mean() * 100
    count = df.groupby("bin", observed=False).buy.size()
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    bars = ax.bar(range(len(share)), share.values, width=0.6, color=BLUE)
    for b, v in zip(bars, share.values):
        ax.annotate(f"{v:.0f}%", (b.get_x() + b.get_width() / 2, v), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.axhline(50, color=MUTED, lw=1)
    ax.set_xticks(range(len(share)), labels)
    ax.set_ylim(0, 108)
    ax.set_xlabel("voucher price minus the smile's fair value (coins)")
    ax.set_ylabel("% of market trades that are buys")
    ax.set_title(f"Market trades lean toward fair value ({len(df):,} voucher trades, days -2 to 0)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "trade_side.png"))
    plt.close(fig)
    return share, count


def chart_basket(prices):
    """Basket vs 2 DRAGONFRUIT + 3 GRANADILLA + 1 MANGOSTEEN over the three days."""
    w = prices[prices["product"].isin(FRUITS + ["FRUIT_BASKET"])].pivot_table(
        index=["day", "timestamp"], columns="product", values="mid_price").reset_index()
    synth = 2 * w.DRAGONFRUIT + 3 * w.GRANADILLA + w.MANGOSTEEN
    x = np.arange(len(w))
    fig, axs = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True, gridspec_kw={"height_ratios": [1.6, 1]})
    axs[0].plot(x, w.FRUIT_BASKET, color=BLUE, lw=1.2, label="FRUIT_BASKET")
    axs[0].plot(x, synth, color=ORANGE, lw=1.2, label="2 DRAGONFRUIT + 3 GRANADILLA + 1 MANGOSTEEN")
    axs[0].legend(loc="upper left")
    axs[0].set_title("The basket follows its fruits tick by tick, but the gap between them drifts")
    thousands(axs[0], decimals=1)
    axs[1].plot(x, w.FRUIT_BASKET - synth, color=BLUE, lw=1.2)
    axs[1].axhline(0, color=MUTED, lw=0.8)
    axs[1].set_ylabel("basket - fruits")
    for ax in axs:
        for b in (10_000, 20_000):
            ax.axvline(b, color=MUTED, lw=0.8)
    axs[1].set_xticks([5_000, 15_000, 25_000], ["day -2", "day -1", "day 0"])
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "basket.png"))
    plt.close(fig)


def voucher_alpha(runs):
    """Each voucher's PnL with the part explained by LYCHEE's moves taken out."""
    out = defaultdict(dict)
    for day in DAYS:
        dbg, pnl = runs[day]["debug"], runs[day]["pnl"]
        drift = defaultdict(float)
        for prev, cur in zip(dbg, dbg[1:]):
            dS = cur["S"] - prev["S"]
            for sym, d in cur["delta_pos"].items():
                drift[sym] += d * dS
        for sym in runs[day]["strat"].VOUCHERS:
            out[sym][day] = pnl[sym] - drift[sym]
    return pd.DataFrame(out).T[DAYS]


def chart_alpha(alpha):
    total = alpha.sum(axis=1)
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    bars = ax.bar(range(len(total)), total.values, width=0.6, color=BLUE)
    for b, v in zip(bars, total.values):
        ax.annotate(f"{v / 1000:.0f}K", (b.get_x() + b.get_width() / 2, v), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(range(len(total)), [s.replace("VOUCHER_", "") for s in total.index])
    ax.set_xlabel("voucher strike")
    ax.set_ylabel("3-day PnL, LYCHEE moves removed")
    thousands(ax)
    ax.set_title("Every strike makes money; the ones near LYCHEE's price make the most")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "pnl_by_strike.png"))
    plt.close(fig)


def chart_cumulative(runs):
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    for day, color in zip(DAYS, (BLUE, ORANGE, AQUA)):
        log = runs[day]["log"]
        curve = log.groupby("timestamp").pnl.sum()
        ax.plot(curve.index / 100, curve.values, color=color, label=f"day {day}: {curve.iloc[-1] / 1000:.0f}K")
    ax.set_xlabel("tick")
    ax.set_ylabel("running PnL")
    thousands(ax)
    ax.legend(loc="upper left")
    ax.set_title("Running PnL of Arham's products: steady climb on all three days")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "cumulative_pnl.png"))
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    runs = run_bot()
    prices, trades = load_prices(), load_trades()
    chart_smile(runs)
    chart_reversion(runs)
    share, count = chart_trade_side(runs, trades)
    chart_basket(prices)
    alpha = voucher_alpha(runs)
    chart_alpha(alpha)
    chart_cumulative(runs)

    mine = runs[0]["strat"].LIMITS
    table = pd.DataFrame({day: {p: v for p, v in runs[day]["pnl"].items() if p in mine} for day in DAYS})
    table["total"] = table.sum(axis=1)
    print("\nPnL by product:\n", table.round(0).to_string())
    print("\nVoucher PnL with LYCHEE's moves removed:\n", alpha.assign(total=alpha.sum(axis=1)).round(0).to_string())
    print("\n% of voucher trades that were buys, by price - fair:\n",
          pd.DataFrame({"% buys": share.round(1), "trades": count}).to_string())
    print(f"\nCharts written to {OUT}")


if __name__ == "__main__":
    main()

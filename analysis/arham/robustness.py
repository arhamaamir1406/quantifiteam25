"""Does the voucher strategy only work for one lucky setting? Re-runs the bot over a grid of
entry/exit thresholds and draws the 3-day PnL as a heatmap (plots/robustness.png).

    python analysis/arham/robustness.py      # ~2 minutes (runs backtests in parallel)
"""
import multiprocessing as mp
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

ENTER = [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
EXIT = [0.5, 1.0, 1.5, 2.0, 2.5]
DAYS = [-2, -1, 0]


def job(args):
    import backtest
    from trader import Trader
    from strategies.fruit_lychee import FruitLycheeStrategy
    enter, exit_ = args
    total = 0.0
    for day in DAYS:
        trader = Trader(only=["fruit_lychee"])
        trader.strategies["fruit_lychee"] = FruitLycheeStrategy({"enter": enter, "exit": exit_})
        pnl, _, _ = backtest.run_day(trader, day)
        total += sum(v for p, v in pnl.items() if p in FruitLycheeStrategy.LIMITS)
    return enter, exit_, total


def main():
    import numpy as np
    from style import BLUES, INK, plt
    from matplotlib.colors import LinearSegmentedColormap
    from strategies.fruit_lychee import FruitLycheeStrategy

    with mp.Pool(min(8, os.cpu_count() or 2)) as pool:
        results = pool.map(job, [(e, x) for e in ENTER for x in EXIT])
    grid = np.zeros((len(ENTER), len(EXIT)))
    for e, x, total in results:
        grid[ENTER.index(e), EXIT.index(x)] = total
    cmap = LinearSegmentedColormap.from_list("blues", BLUES)
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    im = ax.imshow(grid / 1000, cmap=cmap, aspect="auto", origin="lower")
    ax.grid(False)
    for i in range(len(ENTER)):
        for j in range(len(EXIT)):
            v = grid[i, j] / 1000
            dark = v > (grid.min() + 0.6 * (grid.max() - grid.min())) / 1000
            ax.text(j, i, f"{v:.0f}K", ha="center", va="center", fontsize=8, color="white" if dark else INK)
    ax.set_xticks(range(len(EXIT)), [str(x) for x in EXIT])
    ax.set_yticks(range(len(ENTER)), [str(e) for e in ENTER])
    ax.set_xlabel("exit: close once price is this far past fair (coins)")
    ax.set_ylabel("enter: open when price is this far from fair")
    p = FruitLycheeStrategy.PARAMS
    ax.set_title(f"Every setting makes {grid.min() / 1000:.0f}K-{grid.max() / 1000:.0f}K over 3 days "
                 f"(ours: enter {p['enter']}, exit {p['exit']})")
    fig.colorbar(im, ax=ax, label="3-day PnL (thousands)")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "plots", "robustness.png"))
    print("min %.0f  max %.0f  ours %.0f" % (grid.min(), grid.max(),
          grid[ENTER.index(p["enter"]), EXIT.index(p["exit"])]))


if __name__ == "__main__":
    main()

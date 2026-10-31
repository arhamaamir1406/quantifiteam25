# Ali2: stress-tested improvements to Ali's products (Oct 31 2026)

Ali's `strategies/core.py` (commit 4e30d63) made **59,993** over days -2/-1/0 in our backtester.
Ali2 makes **138,207**, and beats Ali's version on every test below for every product with an edge.
The full team file (Ali2 + Arham's fruit_lychee) makes **350,325** locally.

## How we tested
Every candidate had to beat Ali's original on:

| test | what it catches |
|---|---|
| the 3 days -2 / -1 / 0 | basic improvement |
| 6 half-days (each day split in two, starting fresh) | luck: more test samples |
| 3-way rotation: pick settings on 2 days, score the 3rd | overfitting |
| neighbouring settings | a setting that only works at one exact value |
| TOFFEE's whole day shifted +25 / -25 (6 days) | the scoring day sitting at a different level |
| TOFFEE jumping +30 / -30 halfway through the day (6 days) | a level change mid-day |
| every product mirrored upside down | a strategy that only works on uptrends (all strategies scored the same mirrored, so they're symmetric) |
| fuzz: 3,000 ticks with missing book sides/products and positions at the limits | crashes, limit breaches |

## Results (PnL on days -2 / -1 / 0)

| product | Ali | Ali2 | change | Ali2 beats Ali on |
|---|---:|---:|---:|---|
| AMETHYST | 347 / 396 / 332 | 527 / 608 / 478 | +538 | all 12 tests |
| TOFFEE_CAKE | 8,701 / 13,196 / 14,966 | 22,277 / 21,382 / 21,736 | **+28,532** | **all 24 tests**, incl. shifted and jumping levels |
| PAPER_LANTERNS | 9,273 / 10,204 / 8,447 | 19,153 / 18,159 / 18,154 | **+27,542** | all 12 tests |
| TELLURIUM | -6,420 / 2,269 / 2,235 | 1,274 / 5,680 / 7,313 | **+16,183** | all 12 tests |
| JELLY | -1,534 / -110 / -1,044 | -488 / 178 / 415 | +2,792 | 3/3 days (no edge: risk cut, see below) |
| PEANUT_BUTTER | -2,098 / 2,921 / -2,088 | -346 / 1,710 / -3 | +2,626 | 2/3 days (no edge: risk cut, see below) |
| **total** | **59,993** | **138,207** | **+78,214** | |

Rotation (settings picked on 2 days, scored on the 3rd) vs Ali on the held-out days: TOFFEE +27.2K,
LANTERNS +27.5K, TELLURIUM +14.9K.

## What changed and why
- **TOFFEE_CAKE**: same take-then-quote logic as Ali; two numbers changed.
  - The fair value was an EMA over 500 ticks starting at the first price. TOFFEE snaps back within
    ~100 ticks, so that EMA followed the price around and missed half of each bounce.
  - Ali2 starts the EMA at **5,000** (TOFFEE averaged 5,002-5,004 every day) and makes it very slow
    (4,000 ticks), with take 8 → 10.
  - Rejected: a hard-coded fair of exactly 5,000. It made the most (67-73K), but lost to Ali by up to
    7.3K/day when TOFFEE's level was shifted by 25. The slow EMA from 5,000 still follows a shift, and
    beat Ali on all 24 test days.
- **PAPER_LANTERNS**: trends continue (100-tick moves repeat with correlation +0.77).
  - Ali bet on the trend with a target position (27.9K).
  - Ali2 prices the trend into fair value: fair = EMA20 + 0.75 × (its rise over the last 100 ticks).
    It then takes anything 1 past fair and otherwise sits on the best bid/ask.
  - Every setting with k 0.5-1.0 and lookback 100-200 beat Ali on every test (45-55K).
- **TELLURIUM**: Ali's trade-flow signal didn't help (-1.9K; -1.3K with it switched off). Sitting
  on the best bid/ask with a cap of 6 is positive every day. Caps 4-8 all beat Ali on every test;
  cap 15 swings with the 100-380 jumps.
- **AMETHYST**: take anything through 10,000, otherwise sit ON the best bid/ask. Quoting 1 tick
  inside them (the starter code) got filled less.
- **JELLY / PEANUT_BUTTER**: random walks with no edge. Nothing beats Ali on every half-day, because
  either way the result is mostly luck. We kept Ali's quoting and cut the size so the luck is smaller:
  - JELLY: cap 25 → 3, size 5 → 2. Swing (sd over 9 segments) 997 → 360, worst -1,575 → -488.
  - PB: cap 15 → 3, size 3 → 2, edge 2 → 4. Swing 2,028 → 755, worst -2,579 → -468.

## Safety (built Team25QuantiFi2026.py)
- Fuzz test: 0 crashes and 0 limit-breaking order lists in 3,000 damaged ticks.
- Speed: 0.23 ms per tick on average, 1 ms max.
- traderData: at most 881 characters.

## Files
- `make_scenarios.py` builds the stress-test days.
- `core_lab.py` runs every variant side by side.
- `runner.py` is the cached backtest runner.
- `round1.py` and `round2.py` produce `round*_results.txt`.
- `verify_final.py` checks the final core.py gives exactly the lab's numbers: 0 mismatches over 144 product-days.
- `safety.py` runs the fuzz, speed and memory tests.

The scripts expect a scratch copy of the repo with these files in `lab/` (they write extra data
files and swap strategies/core.py), so don't run them inside the repo.

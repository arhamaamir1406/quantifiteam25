# Sepehr2: pattern-based strategies for the pearls (Oct 31 2026)

Sepehr's `strategies/pearls.py` (commit 976811a) made **7,034** over days -2/-1/0 in our backtester.
Sepehr2 makes **64,850**. The full team file (Ali2 + Arham's fruit_lychee + Sepehr2) makes **415,176** locally,
and every one of the 26 products now trades.

## What each pearl does (the same on all 3 days)
| pearl | pattern | evidence |
|---|---|---|
| PINK | The five mids add up to **50,000** (sd ~5). When they don't, PINK is the one that moves to close the gap. | PINK closes 24% / 40% / 70% / 90% of the gap within 10 / 20 / 50 / 100 ticks. The other four pearls don't react (corr ~0). |
| BLUE | **Sawtooth**: creeps up ~0.07 per tick, then every ~1,000 ticks drops ~45 within 30-50 ticks. | 10 / 10 / 9 drops per day and no sharp rises. Once a 5-tick fall of 8+ starts, the next 10 ticks average -14. |
| GOLDEN | **Flat levels**: 8000 all of day -2, then slides to 7900 (day -1), 7800 and 7750 (day 0), at 1-2 per tick over ~50 ticks. | The book sits at level-2/-1 and level+1/+2 and never quotes through the level. |
| WHITE, BLACK | Random walks. | No autocorrelation at any horizon, no jumps. |

`explore.py`, `explore2.py`, `blue.py`, `blue2.py` and `others.py` reproduce these numbers. They need pandas.

## Where Sepehr's 7,034 came from
`decomp.py` splits PnL into "earned by the quotes" vs "price moved while holding inventory". The quotes earned
only ~110-220 per product per day. The rest was holding luck: for example, +3,295 on WHITE on day -1 came
from being short while WHITE fell 460. BLACK and BLUE were switched off.

## The strategies
- **PINK**: fair = (sum target) - (the other four mids), priced halfway (PINK only closes ~70% of the gap in
  50 ticks). Take anything 1 past fair, otherwise rest on the best bid/ask. The sum target starts at 50,000 and
  follows the real sum slowly (EMA 5000), so a scoring day whose total is a bit off doesn't break it.
- **BLUE**: when BLUE moves 12+ within 10 ticks, ride the move at the full limit until it makes no new extreme
  for 10 ticks (or bounces 10). Between moves, hold the full limit in the direction of the creep, measured live
  as an EMA of tick moves outside the sharp moves. It changes position by taking the best quote. Resting
  passively to get out after a drop was much worse in every test.
- **GOLDEN**: on a flat level, take/quote 1 around it (like AMETHYST, cap 5). When mid leaves the level by 3+,
  ride the slide at the full limit until it makes no new extreme for 6 ticks; then that's the new level.
- **BLACK**: sit on the best bid/ask, holding at most 1 (for breadth; no edge to earn).
- **WHITE**: Sepehr's code, unchanged.
All three new ideas work in both directions (rises as well as drops), which is why the mirrored days score the same.

## Results (PnL on days -2 / -1 / 0)
| product | Sepehr | Sepehr2 | change |
|---|---:|---:|---:|
| PINK | 1,074 / 384 / 330 | 10,192 / 8,165 / 8,741 | **+25,310** |
| BLUE | 0 / 0 / 0 | 6,133 / 10,664 / 10,950 | **+27,747** |
| GOLDEN | 106 / 217 / 453 | 125 / 1,998 / 2,762 | +4,109 |
| BLACK | 0 / 0 / 0 | 288 / -38 / 400 | +650 |
| WHITE | 773 / 3,432 / 265 | unchanged | 0 |
| **total** | **7,034** | **64,850** | **+57,816** |

## How we tested (`round1.py`, `round2.py`, 33 test days per variant)
| test | Sepehr2 vs Sepehr (whole pearls book) |
|---|---|
| 3 days | 3/3 |
| 6 half-days (each starts flat) | 6/6 (8.4K-14.4K each) |
| mirrored prices (rises become drops) | 3/3, same PnL |
| PINK's sum shifted +10 / -10 all day | 6/6 (a hard-coded 50,000 fails 3 of these) |
| GOLDEN steps -100 / +100 mid-day | 6/6 |
| **wrong world**: BLUE without the sawtooth (random walk) | 2/3. BLUE alone: -2,770 / +1,476 / -890 |
| **wrong world**: PINK ignoring the sum (random walk) | 3/3. PINK alone: -2,234 / -3,908 / -133 |
| **wrong world**: GOLDEN fake slide (-50 then straight back) | 3/3. GOLDEN alone still +1.1K to +3.9K |

- **Neighbouring settings**: flat plateaus everywhere.
  - PINK: every take 1-3 / make 1-2 / weight 0.5-1 / sum window 2000-10000 makes 25-28K, positive on all 6 half-days.
  - GOLDEN: every guard 2-4 / quiet 3-12 / cap 3-10 makes 4.9-5.2K.
  - BLUE: every detector tried (window 5-15, quiet 6-15, hold 10-20) makes 14-33K, positive on all 6 half-days.
- **Rotation** (pick the best setting on 2 days, score the 3rd): it always beats Sepehr on the held-out day.
  - PINK and BLACK pick the same setting every time.
  - GOLDEN picks guard 2 / cap 10, within ~150 of ours.
  - BLUE picks the faster detector (5 ticks, trigger 8), which makes ~5K more in-sample. We rejected it: on the
    no-sawtooth days it loses 18-23K over 3 days, vs 2K for the chosen 10-tick / 12 detector.
- **If we're wrong**: losing all three patterns at once costs roughly -2K to -4K per product per day. That's
  small next to the +8K to +11K per day each makes when the pattern is there.

## Safety (built Team25QuantiFi2026.py: Ali2 + Arham + Sepehr2)
- Fuzz: 0 crashes and 0 limit-breaking order lists over 3,000 damaged ticks.
- Speed: 0.27 ms per tick on average, 0.93 ms max.
- traderData: at most 1,404 characters.
- `verify_final.py`: the final pearls.py gives exactly the lab's numbers, 0 mismatches over 165 product-days.

## Files
- `pearls_lab.py`: every variant (its defaults reproduce Sepehr's file exactly).
- `runner.py`: the cached backtest runner.
- `report.py`: the comparison table.
- `make_scenarios.py` / `make_wrong.py`: build the stress and wrong-world days.
- `round1.py`, `round2.py`: produce `round*_results.txt`.
- `verify_final.py`, `safety.py`.

The scripts expect a scratch copy of the repo with these files in `lab/` (they write extra data files and swap
strategies/pearls.py), so don't run them inside the repo.

## Still to check
Every new strategy takes liquidity (crosses the spread). Our backtester has only been matched to utefa.com on a
passive-only bot, so upload the built file and compare against the numbers above.

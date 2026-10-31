# Does LYCHEE drift back to a "home" price? (Oct 30 2026)

## 1. Statistics: "probably, but not proven"
- ADF test on 100-tick samples, all 3 days: t = -2.80. The 5% critical value is -2.86, so this just misses.
  By day: -1.26 / -0.94 / -2.98.
- Variance ratio, using 10-tick moves as the base (removes the tick bounce): 0.69 at 1000 ticks and 0.47 at 3000 ticks.
- Monte Carlo with 400 pure random walks of the same step size: 9-10% of them look at least as
  "leashed" as LYCHEE (19% on VR(3000)). So luck explains it about 1 time in 10.
- OU fit of the home price per day: 7433 / 7446 / 7428 (similar each day). Half-life: 1541 / 3139 / 520 ticks.
- Realized volatility falls with horizon: ~122/day from 10-tick moves and ~84/day from 3000-tick moves.
  That's another mean-reversion signature. The vouchers imply ~157/day.
- Prior: QuantiFi copies Prosperity 4, whose underlying (Velvetfruit) mean-reverted by design.

## 2. Strategy test: tune on days -2/-1, check on day 0
- **Fading with LYCHEE itself** (crossing its ~4-wide spread): the best settings make ~+2K/day and hold up on
  day 0 (+2.3K), but the median setting loses ~7K/day to costs. Weak.
- **Fading through the vouchers** (`fruit_lychee_with_fade_CANDIDATE.py`): the existing exposure shading
  steers total LYCHEE exposure toward a target instead of toward 0. Target = -fade_n × clip((S - home)/fade_w, -1, 1).
  Home is the mean of the training days (7437.2), updated as a very slow running mean (fade_hold=100000).
  LYCHEE's own quotes are centred on the target (fade_lychee=1).
  - Grid of fade_n 50-200, fade_w 60-150, skew 0.05/0.1: every setting improved both training days,
    and 17 of 18 improved day 0.
  - A home price 20-40 off still improves day 0 in 19 of 20 settings. Too high (+40) hurts most.

| fade_n | day -2 | day -1 | day 0 (unseen) |
|---:|---:|---:|---:|
| 100 | +6,658 | +5,773 | +6,762 |
| 150 | +11,812 | +7,985 | +9,622 |
| 200 | +13,014 | +10,914 | +10,681 |

(Change vs the committed 181,784 version: fade_w=60, delta_skew=0.05, fade_hold=100000, fade_lychee=1.)

## 3. Risk if we're wrong
This uses an idealised directional PnL (full target exposure, no costs) on 2,000 simulated scoring days
starting from day 0's close (7406), with home 7436:
- **No leash (random walk):** mean +0.6K, sd 19K, 5th percentile -36K, 27% chance of losing more than 10K.
- **Leash is real (OU, half-life 1500):** mean +21K, 5th percentile +10.6K, never loses.

In the real backtest the vouchers only reach part of the target, so the gain is about half the idealised one,
and the risk should be roughly half too.

Scripts: `lychee_stats.py`, `lychee_fade_sim.py`, `lychee_risk.py`, `grid.py` (run them from a scratch
copy of the repo with `FL_PARAMS='{...}'`).

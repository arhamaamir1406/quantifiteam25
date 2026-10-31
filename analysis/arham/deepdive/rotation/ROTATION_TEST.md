# Rotation tests for Arham's strategy (Steps 1-2, Oct 30 2026)

**Method:** three rotations. Tune on days -1/0 and test on -2, tune on -2/0 and test on -1, and tune on
-2/-1 and test on 0. Each held-out day is scored only with settings and home prices taken from the
other two days. All numbers are changes vs the committed bot (60,720 / 62,807 / 58,256 = 181,784).

Raw outputs are in the `*_results.txt` files. To reproduce, run
`ROT_WORK=<scratch dir> python analysis/arham/deepdive/rotation/<script>.py` from the repo root.
`runner.py` caches every backtest in `cache.jsonl`, so reruns are instant and a crash loses nothing.

## Step 1a: LYCHEE lean (step1_lychee.py)
Home price for each rotation = the average LYCHEE price of its 2 training days (7421.7 / 7448.7 / 7437.2).

| size (w=60) | test -2 | test -1 | test 0 |
|---:|---:|---:|---:|
| 100 | +7,074 | +7,147 | +6,762 |
| 150 | +12,836 | +10,905 | +9,622 |
| 200 | +15,257 | +12,669 | +10,681 |
| 300 | +18,166 | +16,472 | +15,274 |

- **All 72 settings (sizes 50-300 × widths 40-120) improved the held-out day in all 3 rotations.**
- Letting training pick always chooses the biggest size (250-300). Bigger always looked better on
  these 3 days, so the size decision is about risk, not about what backtests best.
- Caveat: on each of the 3 days, LYCHEE ended the day having moved toward ~7,436, and a pure random
  walk does that 1 time in 8. The rotation shows the home price is stable across days; it can't prove
  the scoring day behaves the same.

## Step 1b: voucher settings (step1_vouchers.py, lean off)
If training re-picks each setting, the held-out days get **worse** or stay equal:

| setting | held-out change (3 rotations) |
|---|---:|
| enter/exit | -11,417 |
| flow_weight | -5,034 |
| flow_halflife | -6,325 |
| delta_skew | 0 |
| skew_cap | +45 |
| smile_halflife | +2,951 (one rotation negative) |

So the committed settings are already in a good spot, and re-tuning them would be overfitting.
Small settings changes move a single day by ±2-5K, so that's the noise floor.

## Step 1c: lean ON (step1_combined.py)
- Shading strength 0.05 with cap 5 is still right with the lean on (0.03 reaches too little of the target; 0.08-0.1 is no better).
- **Wrong-way test** (lean reversed = what a day where LYCHEE moves AWAY from home looks like at real scale):

| size | test -2 right / wrong | test -1 | test 0 |
|---:|---:|---:|---:|
| 100 | +7.1K / -5.9K | +7.1K / -11.0K | +6.8K / -11.7K |
| 150 | +12.8K / -10.0K | +10.9K / -12.0K | +9.6K / -15.6K |
| 200 | +15.3K / -12.4K | +12.7K / -14.0K | +10.7K / -17.9K |

  If there is no leash, the lean is a coin flip worth about -0.7K/day on average at size 150, with
  bad days of about -10K to -16K. If the leash is real, it's worth about +11K/day.
  Going from 150 to 200 adds +1.7K on good days but -2.5K on bad days, so 150 is the better trade-off.

## Step 2: per-strike offset on top of the smile (offsets.py, step2_offsets.py)
- Each strike's average gap from the smile is 0-2 coins (vs wobbles of 2-6), and its autocorrelation
  after 1000 ticks is ~0. Some strikes lean the same way every day (7000 and 7900 high, 7400 low).
- Held-out results: the prior offset from the training days goes -1.6K to +1.8K per day (sum -0.8K at weight 1).
  Live learning with half-life 3000 gives +1.8K / +0.3K / +2.8K, but that's within the noise. 1 in 8 of the
  variants tested would go 3-for-3 by luck, and its neighbour (half-life 1000) loses.
  **Not adopted.**

## Final candidate (not yet applied; waiting for the user's size choice)
Committed bot + lean: fade_n = size, fade_w 60, fade_anchor **7435.9** (average of all 3 days, for the
scoring day), fade_hold 100000, fade_lychee 1. Everything else is unchanged.
In-sample backtest (the home uses all 3 days, so this is optimistic):

| size | day -2 | day -1 | day 0 | total |
|---:|---:|---:|---:|---:|
| 0 (now) | 60,720 | 62,807 | 58,256 | 181,784 |
| 100 | 67,521 | 68,588 | 65,036 | 201,145 |
| 150 | 72,780 | 71,052 | 68,288 | 212,120 |
| 200 | 73,844 | 73,135 | 69,208 | 216,187 |

# Arham's products: findings, strategy, results

Products: DRAGONFRUIT, GRANADILLA, MANGOSTEEN, FRUIT_BASKET, LYCHEE, and the 10 LYCHEE vouchers
(VOUCHER_6800 … VOUCHER_8100). Code: `strategies/fruit_lychee.py`. Every number and chart here
can be regenerated with:

```bash
pip install pandas matplotlib                # analysis only; the bot itself is plain Python
python analysis/arham/make_plots.py          # numbers + charts in plots/ (~20 s)
python analysis/arham/robustness.py          # parameter heatmap (~2 min)
```

## Summary (abstract-ready)

> The ten LYCHEE vouchers are priced like Black-Scholes call options, and their implied
> volatilities lie on a smooth smile across strikes. Each voucher's price wanders a few coins
> away from that smile and returns within a few hundred ticks. The market's own trades confirm
> this: 93-98% of trades are buys when a voucher sits more than one coin below our fair value,
> and 2-11% are buys when it sits more than one coin above. Every tick, we fit one smile across
> all strikes and smooth it over time. We price each voucher off that smile, nudge the price
> using recent trade flow, and take positions when the market price is at least 3.5 coins away.
> We control the portfolio's exposure to LYCHEE by shading fair values instead of paying to
> hedge, which halves the exposure for about 1% of profit. LYCHEE, the three fruits and the
> basket behave like random walks, and nothing we tested predicts their next move. For them we
> only provide liquidity at the best bid and ask, with small position caps. In our backtest the
> strategy makes **+60.7K / +62.8K / +58.3K** on days -2 / -1 / 0. Parameters were tuned on
> days -2 and -1 and checked on day 0, and every nearby setting makes 170K-184K over the three days.

## Results (our backtester, `python backtest.py --only fruit_lychee`)

| product | day -2 | day -1 | day 0 | total |
|---|---:|---:|---:|---:|
| 10 vouchers | 60,145 | 62,285 | 58,015 | 180,445 |
| LYCHEE | 529 | -281 | 638 | 886 |
| 3 fruits + basket | 46 | 803 | -396 | 453 |
| **total** | **60,720** | **62,807** | **58,256** | **181,784** |

Per-voucher PnL with LYCHEE's moves removed ("what the strategy earned, not luck"): every strike
is positive on every day. The total is 188K over 3 days, ranging from 1.3K (VOUCHER_6800) to 34K
(VOUCHER_7400). See `plots/pnl_by_strike.png` and `plots/cumulative_pnl.png`.

## 1. Vouchers: the main source of profit

### What the data shows
- **One smile.** We backed out each voucher's implied vol (Black-Scholes, no interest rate, time
  in days). Plotted against moneyness `ln(K/S)/sqrt(T)`, all ten strikes fall on one parabola
  (`plots/smile.png`). Its level drifts slowly (about 1.9% per sqrt-day on days -2/-1 and 2.1%
  on day 0), and the wings are higher than the middle.
- **Each strike wobbles on its own.** Changes in one strike's vol are almost uncorrelated with
  the other strikes' (correlation about 0.05 over 20 ticks). So fitting the smile across all
  ten strikes averages the wobble out, and what's left over is the mispricing.
- **The wobble snaps back.** If a voucher is `r` coins off fair value, on average 44% of `r`
  is gone 100 ticks later and about 70% is gone 300 ticks later (correlation of `r` with the
  next 100-tick move: -0.46).
- **Market trades confirm it** (`plots/trade_side.png`). When a voucher is cheap (price below
  fair), 93-98% of trades are buys. When it's rich, 2-11% are. So the trade side is a second,
  independent estimate of where fair value is.
- LYCHEE leads nothing and lags nothing. Vouchers react to LYCHEE in the same tick.

### The strategy (`vouchers()` and `revert()`)
1. Compute each voucher's implied vol from its mid price (Newton's method, plain `math`).
2. Fit `vol = a + b·x + c·x²` through the ten points (`x` = moneyness). Smooth `a, b, c` with
   an exponential average (half-life 200 ticks).
3. Fair value = Black-Scholes at the smile's vol, plus 0.3 coins per recently traded unit
   (buys push it up, sells push it down; half-life 30 ticks).
4. Take positions with one order per side at the worst acceptable price: buy up to the limit
   at `fair − 3.5` and sell up to the limit at `fair + 3.5`. Close a long at `fair + 1.5` and a
   short at `fair − 1.5`. Positions flip 10-40 times a day per strike (`plots/reversion_example.png`).

### Risk: exposure to LYCHEE
Each voucher moves `delta` coins per coin of LYCHEE, so holding vouchers is a hidden LYCHEE bet.
Unmanaged, the portfolio averaged about 82 LYCHEE-equivalents of exposure (about ±11K of daily
noise).
- **Hedging with LYCHEE is too expensive.** Crossing LYCHEE's ~4-coin spread to stay hedged cost
  14K (loose band, 120 units) to 35-55K (tight band, 30 units) over the three days.
- **What we do instead.** Shade every voucher's fair value by `0.05 × exposure × delta`, so new
  trades lean toward shrinking the exposure. This cut average exposure from 82 to 40 (daily
  noise from about 11K to about 6K) and cost about 1K of profit over three days. The shade is
  capped at 5 coins. A much stronger shade (0.4, uncapped) made the book oscillate and lose
  money, which is why the cap exists.

### What we tried that didn't help (or helped less)
| idea | result |
|---|---|
| Each strike's own vol average as fair value (no smile) | ~49K/day vs ~62K/day for the smile on the training days; trade-side accuracy 90.7% vs 94.2% |
| Fit the smile leaving out the strike being priced | slightly worse (6800 becomes an extrapolation) |
| Cubic smile, vega-weighted fit | no better than the plain parabola |
| Also resting passive quotes at the best bid/ask | +0.3-0.7K over 3 days (folded into "one order per side") |
| Trade-flow nudge | **kept**: +10.5K over 3 days (178K → 188K with LYCHEE moves removed) |
| Exposure via LYCHEE hedging | cost 14-55K over 3 days; replaced by fair-value shading |
| Assumed days-to-expiry 3, 5, 10 or 20 | 186.5K-190K: almost no effect, because the price depends on vol × sqrt(T), which the fit absorbs |

## 2. LYCHEE
LYCHEE behaves like a random walk. Its moves don't predict the next ones beyond a tiny tick-level
bounce, and neither its order-book imbalance nor its trades predict anything. Trades happen at
exactly the best bid or ask and don't hurt the side they hit (average edge per filled unit is
+2 to +3 coins measured 1, 10 and 100 ticks later). So we sit on the best bid and ask with a ±10 position
cap: about +300/day. Larger caps add risk without adding money (cap 40: +724 / −3,002 / +1,498).

## 3. Fruits and basket
- **Basket weights.** Regressing basket price changes on fruit price changes gives
  1.9 / 3.0 / 0.85-1.0, so **FRUIT_BASKET ≈ 2 DRAGONFRUIT + 3 GRANADILLA + 1 MANGOSTEEN**
  (R² 0.70 over 100 ticks). They move together within the same tick, and neither side leads
  the other.
- **But the gap drifts.** Basket − (2D+3G+M) went −779 → +900 → −200 over the three days
  (`plots/basket.png`). An AR(1) test gives a t-stat of only −1.6 (not significant; a half-life
  of 6,600-8,400 ticks if it's real at all). Hedging one basket also needs 2/3/1 fruits, and the
  40-unit limits cap that at about 13 baskets. We judged the arbitrage not worth the risk.
- **What we do.** Join the best bid and ask with a ±1 position cap. Fills earn about +2 coins over
  the next 1-10 ticks, and holding inventory is pure noise (the basket moved +1,700 / +900 / −300
  coins on the three days).
  With a ±3 cap, the basket alone lost on all three days, so we kept the risk minimal.

## Assumptions to check
- **Backtester fill rules.** Our backtester matched utefa.com exactly for `example_trader_1.py`
  (1,613), but that only tests passive joins. The voucher strategy also takes liquidity across
  several book levels in one order. Upload `Team25QuantiFi2026.py` and compare with the
  table above.
- **Days to expiry.** The bot assumes 5 days at the open of the scoring day (8 at day −2 per the
  wiki). This barely matters (see the table above).
- **`state.market_trades`** is assumed to hold the previous tick's market trades. If the site
  gives none, the flow nudge just stays at 0 (about −6%).

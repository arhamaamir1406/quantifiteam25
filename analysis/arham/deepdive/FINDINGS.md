# IMC Prosperity 2/3/4 deep dive: what applies to QuantiFi (Oct 30 2026)

QuantiFi is built like IMC Prosperity, especially **Prosperity 4 (2026)**. For each Prosperity
pattern we checked whether it shows up in our data, then sized it with a quick prototype in our
backtester. The prototypes are `proto.py` and `proto2.py` here. They are throwaway code, not team
code. Run one with:
`cd quantifi && V=2 python backtest.py --file analysis/arham/deepdive/proto.py`
(V picks the variant).

All PnL numbers are **in-sample** (days -2/-1/0) from rough, barely-tuned prototypes. They show
how big an idea is, not what it will score. Treat them as estimates until they're checked on utefa.com.

## Summary

| Product (owner) | Prosperity match | Pattern in OUR data | Prototype PnL, 3 days | Baseline (join best bid/ask) |
|---|---|---|---:|---:|
| TOFFEE_CAKE (Ali) | P4 HYDROGEL / OSMIUM | Snaps back to **5,000** (daily mean 5002-5004, sd ~22, half-life ~80-135 ticks) | **55K-75K** | 3.7K |
| PAPER_LANTERNS (Ali) | P4 PEPPER_ROOT (drift) | **Momentum**: consecutive 100-tick moves correlate +0.77 (200-tick: +0.75) | **47K-51K** | 1.8K |
| PINK_PEARLS (Sepehr) | P4 PEBBLES (sum identity, "lean on XL") | Pearls sum to **50,000** (sd ~5). Only PINK closes the gap: corr(sum gap, PINK's next move) = -0.41; the others ~0 | **15K-22K** | 5.8K |
| TELLURIUM (Ali) | P3 SQUID_INK (jumpy: keep size small) | Huge flow (~4,900 units/day), jumps of 100-280 | **~13.7K** (cap 5-10) | cap 40: -10.6K |
| AMETHYST (Ali) | P2 AMETHYSTS / P3 RESIN | Pegged at 10,000; the book never quotes through 10,000 | 1.6K (already the max) | 1.6K |
| WHITE/BLACK/BLUE/GOLDEN pearls, JELLY, PEANUT_BUTTER | - | Random-walk-like; no strong edge found | small (+/-) | small |
| Vouchers (Arham) | P3 VOLCANIC_ROCK (IV scalping) | Already done: smile fit + reversion | 180K (current) | - |
| LYCHEE (Arham) | P3/P4 underlying mean reversion | Hints only (VR 0.56 at 1000 ticks); **next test** | - | - |
| Fruits + basket (Arham) | P2/P3 basket arb | Does NOT apply: our gap drifts (VR 1.31), P2/P3 gaps reverted | - | - |

Rough team potential: ~182K (Arham, current) + ~150K from the four leads above, so **~330K**
in-sample, up from ~184K today.

## Details

### TOFFEE_CAKE: mean reversion around 5,000
- Fair = 5000. Take asks <= fair-8 and bids >= fair+8. Rest quotes at no closer than fair±4.
  This gives 21.9K/22.2K/23.5K per day. Other settings (take 3-12, make 1-6) give 55-75K
  over 3 days, which is a flat plateau and a good sign it isn't overfit.
- **Robustness:** with a slow EMA anchor (alpha 1/2000) instead of a hard-coded 5000 it still
  makes 52K. Use that if the scoring day might sit at a different level.
- The spread is wide (~15), so passive fills are worth a lot. The market's own trades at the bid
  when the price is low earn ~27 per trade within 10 ticks.

### PAPER_LANTERNS: momentum (trend continuation)
- The price is a smooth trend plus tick noise: ac1 of tick moves is -0.5, but 50/100/200/500-tick
  moves correlate +0.58/+0.77/+0.75/+0.28 with the previous move of the same length.
- Fair = EMA20(mid) + 0.75 × (EMA change over the last 200 ticks). Take ±2, make ±1. This
  gives about 16K/day on every day. k = 0.5-1.0 and EMA length 20-40 all give 47-51K.
  With k = 0 (smoothing only) it makes just 2.3K, so **the momentum is the edge**.
- The real bot must keep its EMA history in `traderData`, not in instance variables (IMC
  re-creates the Trader object).

### PEARLS: sum = 50,000, and PINK is the one that adjusts
- Sum of the 5 mids: mean 50,000, sd ~5, every day. Full 5-leg arbitrage is almost never possible
  (sum of bids > 50,000 in only ~20 ticks a day, by at most 3).
- When the sum is off, **PINK** moves to fix it (corr -0.41 over the next 10 ticks, all 3 days).
  The other four don't respond.
- So: PINK fair = 50,000 − (sum of the other four mids). Taking ±2 and making ±1 gives
  8.3K/7.2K/6.8K. Using the same fair for the OTHER pearls loses 10-30K each, so don't.
- GOLDEN_PEARLS sits on plateaus (8000 all of day -2, then 7900, 7800, 7750) and steps down
  without snapping back.

### TELLURIUM
- Join the best bid/ask with a small cap: cap 5 gives 13.7K (1.4K/5.4K/7.0K) and cap 10 gives 13.4K.
  Cap 40 swings from -20K to +25K per day because of the 100-280 jumps. This matches the P3
  Squid Ink lesson: keep size small on jumpy products.

### What did NOT transfer
- **Wall-mid / taking mispriced quotes (P2/P3):** our books have no deep "wall" level, and taking
  quotes that cross the wall-mid loses 1-4 per unit. The simulated book is symmetric noise around fair.
- **Basket arbitrage (P2 gift basket, P3 picnic baskets):** their basket-minus-components gap
  reverted to a fixed premium. Ours wanders (-779 → +900 → -200). Rejected.
- **Counterparty signals (P2 R5, P3 "Olivia", P4 "Mark 67"):** our buyer/seller columns are always blank.
- **Deep-OTM bid-0 trick (P4):** our deepest voucher (8100) trades at 2-44, not 0/1.
- **JELLY/PEANUT_BUTTER pair (P4 SNACKPACK-style):** their moves correlate (+0.71), but the
  spread's half-life is 336-2,108 ticks and unstable. Not worth it.

## Risks the winners hit
- **Mean reversion decays out of sample:** P4's Velvetfruit fade fell from ~39K to ~17K on the
  held-out day; P3 Frankfurt's underlying fade went +100K / -50K / -10K. That matters for
  TOFFEE and for the LYCHEE test.
- **The smile can break on the scoring day (P3 CMU):** a rolling per-strike IV was their fix. In our data
  per-strike IV is worse (49K vs 62K/day), but a fallback is worth considering.
- **Prefer flat parameter regions** over the best backtest number, and never tune to the website score
  (P3 Frankfurt).

## Sources
- P4: github.com/Durpie-Git/imc-prosperity-4 (#4), github.com/FoxHenderson/imc-prosperity-4 (#10),
  github.com/nathanw3456/Prosperity_4_Writeup, github.com/heckop/imc-prosperity-4-writeup
- P3: github.com/TimoDiehm/imc-prosperity-3 (Frankfurt Hedgehogs, #2), github.com/chrispyroberts/imc-prosperity-3 (#7)
- P2: github.com/ericcccsliu/imc-prosperity-2 (Linear Utility, #2)

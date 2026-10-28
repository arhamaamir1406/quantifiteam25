# QuantiFi 2026 — Team 25

Our trading bot for UTEFA's QuantiFi competition. Rules and data come from the
[QuantiFi Wiki](https://docs.google.com/document/d/17x1A0EeAXjQNNJ0P_bWYXQskdVymS86AIXJ3w9jaBAE/edit).

**Due Sun Nov 1, 11:59 PM:** `Team25QuantiFi2026.py` (made by `build.py`) + `Team25QuantiFi2026.pdf` (abstract, max 5 pages), submitted by the team lead through the Google Form.

## Who owns what

| File | Owner | Products |
|---|---|---|
| `strategies/core.py` → `CoreStrategy` | Ali | AMETHYST, TOFFEE_CAKE, PAPER_LANTERNS, TELLURIUM, JELLY, PEANUT_BUTTER |
| `strategies/fruit_lychee.py` → `FruitLycheeStrategy` | Arham | DRAGONFRUIT, GRANADILLA, MANGOSTEEN, FRUIT_BASKET, LYCHEE, VOUCHER_6800 … VOUCHER_8100 |
| `strategies/pearls.py` → `PearlStrategy` | Sepehr | WHITE_PEARLS, BLACK_PEARLS, GOLDEN_PEARLS, PINK_PEARLS, BLUE_PEARLS |
| `strategies/common.py` | shared (tell everyone before changing) | helper functions |
| `trader.py` | shared (tell everyone before changing) | calls the 3 classes every tick |
| `backtest.py`, `build.py` | shared tools | — |
| `datamodel.py`, `data/`, `examples/` | UTEFA's, never edit | — |
| `analysis/<your name>/` | you | your notebooks, plots for the abstract |

## How the bot works

Every tick UTEFA calls `Trader().run(state)`. `trader.py` passes `state` (all 26 order books, our positions, recent trades) to each strategy class's `trade(state, mem)`. Each class returns `{product: [Order(product, price, quantity), ...]}` for its own products (quantity > 0 buys, < 0 sells). `trader.py` trims anything that would break a position limit and returns all the orders.

`mem` is your class's private memory (a dict). Whatever you put in it comes back on the next tick, because `trader.py` saves it in `traderData`. Keep it small (e.g. the last 50 prices, not the whole day).

## Commands

```bash
python backtest.py --only pearls        # test just your strategy (core / fruit_lychee / pearls)
python backtest.py                      # test the whole team's bot
python backtest.py --days -2 -1         # tune on these days...
python backtest.py --days 0             # ...then check on day 0 without changing anything
python backtest.py --log results/x.csv  # per-tick position + PnL, for plots
python build.py                         # make Team25QuantiFi2026.py and test it (the file to upload)
```

`backtest.py` copies UTEFA's fill rules from the wiki. The rules it has to guess are marked `ASSUMPTION` at the top of the file. `examples/example_trader_1.py` makes **527 / 608 / 478** here on days −2 / −1 / 0. If UTEFA's website shows different numbers for that file, our backtester needs fixing before anyone trusts it.

## Team rules

1. **Only edit your own strategy file** (and your `analysis/` folder). Shared files change only after telling everyone.
2. **Keep all your code inside your class.** No top-level functions or variables: `build.py` pastes every file into one, and same-named things would clash. `build.py` stops with an error if they do.
3. **Tune on days −2 and −1, check on day 0.** Day 0 stands in for the secret scoring day. Build on how a product *behaves* (stays near a price, follows another product), not on where it *happened to go*.
4. **Plain Python only** (`math`, `json`, `statistics`, `typing`) until UTEFA confirms numpy/pandas are allowed on their server.
5. Pull `main` into your branch every day so you test against everyone's latest code.

## Git workflow

```bash
git checkout <your-name>          # once: switch to your branch (ali / arham / sepehr)
git pull origin main              # daily: bring in everyone's merged work
# ...edit your strategy, run python backtest.py --only <yours>...
git add strategies/<your-file>.py
git commit -m "pearls: explain what changed"
git push origin <your-name>
```

When your version beats what's on `main`, open a Pull Request from your branch into `main` on GitHub.

## Starting point

On the first commit, only AMETHYST trades: it was exactly 10,000 every tick, so buying at 9,999 and selling at 10,001 is safe. It makes about +1,074 over the three days.

`common.market_make()` (quote one tick inside the best bid/ask around the mid price) is available, but on its own it **loses money** on most products. Run on all 26 at full size, it lost about 75,000 over three days, mostly on TELLURIUM and the vouchers. The bot gets filled on the side the price is moving toward and ends up holding the maximum while the price runs against it. Adding `skew=1` (back off when already holding a lot) cut that to about −35,000. Every product needs its own idea, not a generic quote.

import json
import math
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional


# ============================================================================
# strategies/common.py
# Shared helpers every strategy can use.
#
# SHARED FILE: don't change it without telling the whole team (it affects everyone).
# build.py pastes this file into the submission first, so these names are
# available to every strategy class below it.
# ============================================================================
def best_bid(depth: OrderDepth) -> Optional[int]:
    return max(depth.buy_orders) if depth.buy_orders else None


def best_ask(depth: OrderDepth) -> Optional[int]:
    return min(depth.sell_orders) if depth.sell_orders else None


def mid_price(depth: OrderDepth) -> Optional[float]:
    bid, ask = best_bid(depth), best_ask(depth)
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2


def market_make(
    product: str,
    depth: OrderDepth,
    position: int,
    limit: int,
    fair: Optional[float] = None,
    edge: float = 1,
    size: Optional[int] = None,
    skew: float = 0,
) -> List[Order]:
    """Baseline strategy: take anything mispriced vs `fair`, then quote 1 tick
    inside the best bid/ask (but never closer than `edge` to fair).

    fair defaults to the current mid price. `size` caps each resting quote.
    `skew` lowers our fair value when we're long (raises it when short) by
    skew x spread at a full position, so we stop piling into a trend.
    Everyone is expected to replace this with something smarter for their own products.
    """
    orders: List[Order] = []
    bid, ask = best_bid(depth), best_ask(depth)
    if bid is None or ask is None:
        return orders
    if fair is None:
        fair = (bid + ask) / 2
    fair -= skew * (ask - bid) * position / limit
    can_buy = limit - position
    can_sell = limit + position

    # 1. Take: buy asks that are clearly below fair, sell into bids clearly above it
    for price in sorted(depth.sell_orders):
        if price > fair - edge or can_buy <= 0:
            break
        qty = min(-depth.sell_orders[price], can_buy)
        orders.append(Order(product, price, qty))
        can_buy -= qty
    for price in sorted(depth.buy_orders, reverse=True):
        if price < fair + edge or can_sell <= 0:
            break
        qty = min(depth.buy_orders[price], can_sell)
        orders.append(Order(product, price, -qty))
        can_sell -= qty

    # 2. Make: rest the remaining capacity just inside the spread
    quote_bid = min(bid + 1, math.floor(fair - edge))
    quote_ask = max(ask - 1, math.ceil(fair + edge))
    if size is not None:
        can_buy, can_sell = min(can_buy, size), min(can_sell, size)
    if can_buy > 0:
        orders.append(Order(product, quote_bid, can_buy))
    if can_sell > 0:
        orders.append(Order(product, quote_ask, -can_sell))
    return orders


# ============================================================================
# strategies/core.py
# ALI's products: AMETHYST, TOFFEE_CAKE, PAPER_LANTERNS, TELLURIUM, JELLY, PEANUT_BUTTER.
#
# Owner: Ali. Only Ali edits this file.
# Rule for build.py: keep ALL your code inside the class (no top-level functions or
# variables), so nothing clashes with the other strategy files once they're pasted together.
#
# Ali2 (Oct 31): Ali's version with changes that beat it on every stress test we ran:
# the 3 days, the 6 half-days, a 3-way rotation (tune on 2 days, test on the 3rd), mirrored
# prices, and TOFFEE moved +-25 or jumping +-30 mid-day.
# Results and scripts: analysis/ali2/ALI2_TEST.md.
# ============================================================================
class CoreStrategy:
    LIMITS = {
        "AMETHYST": 50,
        "TOFFEE_CAKE": 50,
        "PAPER_LANTERNS": 50,
        "TELLURIUM": 40,
        "JELLY": 50,
        "PEANUT_BUTTER": 50,
    }

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        """Called every tick. Return {product: [Order, ...]}.
        `mem` is this file's private memory: whatever you put in it comes back next tick."""
        result: Dict[str, List[Order]] = {}

        # AMETHYST: fixed fair value of 10,000 on every tick of all three training days.
        # Take anything through 10,000, otherwise sit ON the best bid/ask (quoting 1 tick
        # inside them filled less often: 1,075 -> 1,613 over the 3 days).
        book = state.order_depths.get("AMETHYST")
        if book is not None and book.buy_orders and book.sell_orders:
            pos = state.position.get("AMETHYST", 0)
            result["AMETHYST"] = self._take_and_join(
                "AMETHYST", book, pos, self.LIMITS["AMETHYST"], fair=10_000, take=1, make=1)

        result.update(self.toffee_cake(state, mem))
        result.update(self.paper_lanterns(state, mem))
        result.update(self.tellurium(state, mem))
        result.update(self.jelly(state, mem))
        result.update(self.peanut_butter(state, mem))
        return result

    # =====================================================================
    # Helpers (shared by all products)
    # =====================================================================
    def _mid(self, book):
        """Best bid, best ask, mid. Returns None if one side of the book is empty."""
        if book is None or not book.buy_orders or not book.sell_orders:
            return None
        best_bid = max(book.buy_orders)
        best_ask = min(book.sell_orders)
        return best_bid, best_ask, (best_bid + best_ask) / 2

    def _quote(self, P, best_bid, best_ask, pos, fair, edge, size, cap, skew,
               buy_room=None, sell_room=None) -> List[Order]:
        """Resting bid and ask around fair, skewed by position, never above `cap`."""
        if buy_room is None:
            buy_room = cap - pos
        if sell_room is None:
            sell_room = cap + pos
        buy_room = max(0, min(buy_room, cap - pos))
        sell_room = max(0, min(sell_room, cap + pos))

        quote_fair = fair - skew * pos
        bid = min(round(quote_fair - edge), best_ask - 1)
        ask = max(round(quote_fair + edge), best_bid + 1)

        orders: List[Order] = []
        if buy_room > 0:
            orders.append(Order(P, int(bid), min(size, buy_room)))
        if sell_room > 0:
            orders.append(Order(P, int(ask), -min(size, sell_room)))
        return orders

    def _take_and_join(self, P, book, pos, limit, fair, take, make) -> List[Order]:
        """Buy every ask at least `take` below fair and sell every bid at least `take` above it,
        then rest the remaining room ON the best bid/ask (never closer than `make` to fair)."""
        orders: List[Order] = []
        buy_room, sell_room = limit - pos, limit + pos
        for price in sorted(book.sell_orders):
            if price > fair - take or buy_room <= 0:
                break
            qty = min(-book.sell_orders[price], buy_room)
            orders.append(Order(P, price, qty))
            buy_room -= qty
        for price in sorted(book.buy_orders, reverse=True):
            if price < fair + take or sell_room <= 0:
                break
            qty = min(book.buy_orders[price], sell_room)
            orders.append(Order(P, price, -qty))
            sell_room -= qty
        bid = min(max(book.buy_orders), math.floor(fair - make))
        ask = max(min(book.sell_orders), math.ceil(fair + make))
        if buy_room > 0:
            orders.append(Order(P, bid, buy_room))
        if sell_room > 0:
            orders.append(Order(P, ask, -sell_room))
        return orders

    def _join(self, P, book, pos, cap) -> List[Order]:
        """Sit on the best bid and best ask, never holding more than +-cap."""
        orders: List[Order] = []
        if cap - pos > 0:
            orders.append(Order(P, max(book.buy_orders), cap - pos))
        if cap + pos > 0:
            orders.append(Order(P, min(book.sell_orders), -(cap + pos)))
        return orders

    # =====================================================================
    # TOFFEE_CAKE: mean-reverting around ~5,000 (reversion strongest at 500 ticks)
    # =====================================================================
    def toffee_cake(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "TOFFEE_CAKE"
        HOME = 5000        # Ali2: TOFFEE averaged 5,002-5,004 on every training day
        EMA_WINDOW = 4000  # Ali2: was 500, which chased the price and missed half of each bounce
        EDGE = 6           # Step 4: trades happen ~7.5 from mid
        TAKE = 10          # take any quote at least this far past fair (Ali2: was 8)
        SIZE = 10
        SKEW = 0.1

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        book = state.order_depths[P]
        pos = state.position.get(P, 0)
        limit = self.LIMITS[P]

        # 1. fair value: very slow EMA that STARTS at 5,000, so it stays near home but still
        #    follows if TOFFEE settles at a new level (stress test: whole day shifted +-25)
        fair = mem.get("toffee_home", HOME)
        fair += 2 / (EMA_WINDOW + 1) * (mid - fair)
        mem["toffee_home"] = fair

        orders: List[Order] = []
        buy_room = limit - pos
        sell_room = limit + pos

        # 2. take clearly mispriced quotes
        for price in sorted(book.sell_orders):
            if price <= fair - TAKE and buy_room > 0:
                qty = min(-book.sell_orders[price], buy_room)
                orders.append(Order(P, price, qty))
                buy_room -= qty
        for price in sorted(book.buy_orders, reverse=True):
            if price >= fair + TAKE and sell_room > 0:
                qty = min(book.buy_orders[price], sell_room)
                orders.append(Order(P, price, -qty))
                sell_room -= qty

        # 3+4. skewed resting quotes with whatever room is left
        orders += self._quote(P, best_bid, best_ask, pos, fair, EDGE, SIZE, limit, SKEW,
                              buy_room, sell_room)
        return {P: orders}

    # =====================================================================
    # PAPER_LANTERNS: straight-line trends + tick flicker
    # =====================================================================
    def paper_lanterns(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "PAPER_LANTERNS"
        EMA = 20           # smooths the flicker (bounce -0.5)
        LOOK = 100         # Ali2: trends continue; 100-tick moves repeat with correlation +0.77
        STEP = 10          # remember the smoothed price every 10 ticks (keeps traderData small)
        K = 0.75           # fair = smoothed price + K x its rise over the last LOOK ticks
        TAKE = 1           # take any quote at least this far past fair
        MAKE = 1           # rest the rest on the best bid/ask, never closer than this to fair

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        _, _, mid = top
        book = state.order_depths[P]
        pos = state.position.get(P, 0)

        # 1. smoothed price, and where it was LOOK ticks ago
        ema = mem.get("pl_ema", mid)
        ema += 2 / (EMA + 1) * (mid - ema)
        mem["pl_ema"] = ema
        tick = mem.get("pl_tick", 0)
        hist = mem.setdefault("pl_hist", [])
        if tick % STEP == 0:
            hist.append(round(ema, 3))
            del hist[:-(LOOK // STEP + 1)]
        mem["pl_tick"] = tick + 1

        # 2. fair value leans the way the trend is going (Ali2: Ali's fast-slow EMA trend
        #    with a target position made 27.9K; pricing the trend into fair makes 55.5K)
        trend = ema - hist[0] if len(hist) == LOOK // STEP + 1 else 0.0
        fair = ema + K * trend
        return {P: self._take_and_join(P, book, pos, self.LIMITS[P], fair, TAKE, MAKE)}

    # =====================================================================
    # TELLURIUM: jumps of 100-380, so keep size small and just earn the spread
    # =====================================================================
    def tellurium(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "TELLURIUM"
        CAP = 6            # Ali2: caps 4-8 all positive every day; 15+ swings with the jumps

        book = state.order_depths.get(P)
        if self._mid(book) is None:
            return {}
        pos = state.position.get(P, 0)
        # Ali2: the trade-flow fair value lost money (-1.9K; -1.3K with flow off). Sitting on
        # the best bid/ask makes 1.3K / 5.7K / 7.3K on the 3 days.
        return {P: self._join(P, book, pos, CAP)}

    # =====================================================================
    # JELLY: random walk around ~2,000, medium risk
    # =====================================================================
    def jelly(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "JELLY"
        EMA_WINDOW = 50
        EDGE = 4           # trades ~5.5 from mid
        SIZE = 2           # Ali2: was 5
        CAP = 3            # Ali2: was 25. No edge here, so hold less: day-to-day swings 997 -> 360
        SKEW = 0.2

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        pos = state.position.get(P, 0)

        fair = mem.get("jelly_ema", mid)
        fair += 2 / (EMA_WINDOW + 1) * (mid - fair)
        mem["jelly_ema"] = fair

        return {P: self._quote(P, best_bid, best_ask, pos, fair, EDGE, SIZE, CAP, SKEW)}

    # =====================================================================
    # PEANUT_BUTTER: random walk, price moves faster than the half-spread
    # =====================================================================
    def peanut_butter(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "PEANUT_BUTTER"
        EMA_WINDOW = 20    # fast: tick move (3.8) > half-spread (3)
        EDGE = 4           # Ali2: was 2 (quote less eagerly)
        SIZE = 2           # Ali2: was 3
        CAP = 3            # Ali2: was 15. No edge here, so hold less: day-to-day swings 2,028 -> 755
        SKEW = 0.3

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        pos = state.position.get(P, 0)

        fair = mem.get("pb_ema", mid)
        fair += 2 / (EMA_WINDOW + 1) * (mid - fair)
        mem["pb_ema"] = fair

        return {P: self._quote(P, best_bid, best_ask, pos, fair, EDGE, SIZE, CAP, SKEW)}


# ============================================================================
# strategies/fruit_lychee.py
# ARHAM's products: DRAGONFRUIT, GRANADILLA, MANGOSTEEN, FRUIT_BASKET, LYCHEE, and the
# 10 LYCHEE vouchers (call options; symbols in the data are VOUCHER_6800 ... VOUCHER_8100).
#
# Owner: Arham. Only Arham edits this file.
# Rule for build.py: keep ALL your code inside the class (no top-level functions or
# variables), so nothing clashes with the other strategy files once they're pasted together.
#
# What the data showed (analysis/arham/NOTES.md has the numbers and plots):
#   * Vouchers: priced like Black-Scholes calls whose implied vol sits on a smooth "smile"
#     across strikes. Each voucher's price wanders a few coins off that smile and snaps back
#     within a few hundred ticks, and the market's own trades lean the same way (about 90% of
#     trades are buys when a voucher is cheap). So we buy cheap vouchers and sell rich ones.
#   * LYCHEE, the three fruits and FRUIT_BASKET move like random walks (nothing predicts the
#     next move, and the basket ~ 2 DRAGONFRUIT + 3 GRANADILLA + 1 MANGOSTEEN plus a gap that
#     drifts instead of snapping back). Market trades in them happen at the best bid/ask and
#     don't predict the next move, so we just sit on the best bid and ask to earn the spread,
#     with small position caps because holding them is pure risk.
#   * Over hours, though, LYCHEE gets pulled back toward a "home" price of about 7,436 (same
#     home on all 3 days). So we lean the voucher book: hold up to +150 LYCHEE-equivalents when
#     LYCHEE is 60+ below home and -150 when it's 60+ above (rotation test in
#     analysis/arham/deepdive/rotation/ROTATION_TEST.md: improved every held-out day).
# ============================================================================
class FruitLycheeStrategy:
    STRIKES = [6800, 7000, 7200, 7300, 7400, 7500, 7600, 7750, 7900, 8100]
    VOUCHERS = {f"VOUCHER_{k}": k for k in STRIKES}
    FRUITS = ["DRAGONFRUIT", "GRANADILLA", "MANGOSTEEN", "FRUIT_BASKET"]
    LIMITS = {
        "DRAGONFRUIT": 40,
        "GRANADILLA": 40,
        "MANGOSTEEN": 40,
        "FRUIT_BASKET": 40,
        "LYCHEE": 200,
        **{f"VOUCHER_{k}": 50 for k in STRIKES},
    }
    # Tuned on days -2/-1 and checked on day 0; results barely change for nearby values
    # (enter 3-4, exit 1-2, smile_halflife 150-400, flow_weight 0.3-0.5 all land within ~3%).
    PARAMS = {
        "days_to_expiry": 5,  # at the open of the scoring day (it was 8 at day -2, 7 at -1, 6 at 0)
        "smile_halflife": 200,  # ticks; how slowly our estimate of the fair vol smile moves
        "enter": 3.5,  # take a voucher position when the price is this many coins past fair value
        "exit": 1.5,  # close it once the price has come back past fair value by this much
        "flow_weight": 0.0,  # coins each recently traded unit moves fair value (buys up, sells down)
        "flow_halflife": 30,  # ticks; how fast we forget those trades
        "delta_skew": 0.05,  # shade fair values to steer our total LYCHEE exposure toward the lean target
        "skew_cap": 5.0,  # never shade a fair value by more than this many coins
        "lychee_cap": 10,  # quote LYCHEE on both sides, but never hold more than this past the target
        "fruit_cap": 1,  # same for each fruit and the basket
        "lean_size": 150,  # biggest LYCHEE bet (in LYCHEE-equivalents) on the price returning home
        "lean_width": 60,  # how far from home LYCHEE must be for the full bet
        "lean_home": 7435.9,  # LYCHEE's average price over days -2, -1, 0
        "lean_hold": 100000,  # the home also drifts very slowly toward the live price (ticks of weight)
    }

    def __init__(self, params: Optional[dict] = None):
        self.p = dict(self.PARAMS, **(params or {}))
        self.debug: Optional[list] = None  # analysis scripts set this to a list to record exposure

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        """Called every tick. Return {product: [Order, ...]}.
        `mem` is this file's private memory: whatever you put in it comes back next tick."""
        result: Dict[str, List[Order]] = self.vouchers(state, mem)
        center = max(-190, min(190, int(round(mem.get("target", 0)))))  # LYCHEE quotes lean the same way
        result["LYCHEE"] = self.join_quotes("LYCHEE", state, self.p["lychee_cap"], center)
        for sym in self.FRUITS:
            result[sym] = self.join_quotes(sym, state, self.p["fruit_cap"])
        return {sym: orders for sym, orders in result.items() if orders}

    # ------------------------------------------------------------------ vouchers
    def vouchers(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        S = self.mid(state.order_depths.get("LYCHEE"))
        if S is None:
            return {}
        T = max(self.p["days_to_expiry"] - state.timestamp / 1_000_000, 0.1)  # days left
        smile = mem.get("smile")  # [a, b, c]: fair vol = a + b*x + c*x^2, x = 100*ln(K/S)/sqrt(T)

        # 1. Each voucher's implied vol right now (the vol that makes Black-Scholes = its mid price)
        xs, ivs, mids = {}, {}, {}
        for sym, K in self.VOUCHERS.items():
            m = self.mid(state.order_depths.get(sym))
            if m is None:
                continue
            x = 100 * math.log(K / S) / math.sqrt(T)  # how far out of the money, in vol units
            guess = smile[0] + smile[1] * x + smile[2] * x * x if smile else 0.02
            iv = self.implied_vol(m, S, K, T, guess)
            mids[sym], xs[sym] = m, x
            if iv is not None:
                ivs[sym] = iv

        # 2. Fit one smooth smile through all strikes, then average it over recent ticks.
        #    Each strike's own wobble is independent of the others', so the fit averages it out.
        if len(ivs) >= 5:
            fit = self.fit_parabola([xs[sym] for sym in ivs], list(ivs.values()))
            if fit is not None:
                n = mem.get("n", 0) + 1
                a = max(1 - 0.5 ** (1 / self.p["smile_halflife"]), 1 / n)  # plain mean while warming up
                smile = fit if smile is None else [old + a * (new - old) for old, new in zip(smile, fit)]
                mem["smile"], mem["n"] = smile, n
        if smile is None:
            return {}

        # 3. Recent market trades: buyers show up when a voucher is cheap, sellers when it's rich.
        #    flow = recent units bought minus units sold (fading out), nudges fair value that way.
        flow = mem.setdefault("flow", {})
        last_mid = mem.setdefault("mid", {})
        decay = 0.5 ** (1 / self.p["flow_halflife"])
        market_trades = state.market_trades or {}
        for sym in self.VOUCHERS:
            f = flow.get(sym, 0.0) * decay
            for tr in market_trades.get(sym, []) or []:
                if sym in last_mid:
                    f += tr.quantity if tr.price > last_mid[sym] else -tr.quantity
            flow[sym] = round(f, 3)
        last_mid.update(mids)

        # 4. Our total exposure to LYCHEE moves (each voucher moves `delta` coins per coin of LYCHEE).
        #    When it's large, we shade every voucher's fair value so new trades shrink it.
        vols = {sym: smile[0] + smile[1] * x + smile[2] * x * x for sym, x in xs.items()}
        deltas = {sym: self.bs_delta(S, self.VOUCHERS[sym], T, vols[sym]) for sym in xs}
        exposure = state.position.get("LYCHEE", 0) + sum(
            state.position.get(sym, 0) * d for sym, d in deltas.items())

        #    The exposure we steer toward isn't 0: lean against LYCHEE's distance from home
        #    (+lean_size when it's lean_width or more below home, -lean_size when as far above).
        n_home = mem.get("home_n", 0) + 1
        home = mem.get("home", self.p["lean_home"])
        home += (S - home) / (self.p["lean_hold"] + n_home)
        mem["home"], mem["home_n"] = home, n_home
        target = -self.p["lean_size"] * max(-1.0, min(1.0, (S - home) / self.p["lean_width"]))
        mem["target"] = target

        # 5. Fair price = Black-Scholes at the smile's vol (+ flow and exposure nudges); trade the gap
        out, fairs = {}, {}
        cap = self.p["skew_cap"]
        for sym in xs:
            K = self.VOUCHERS[sym]
            fair = self.bs_call(S, K, T, vols[sym]) + self.p["flow_weight"] * flow[sym]
            fair -= max(-cap, min(cap, self.p["delta_skew"] * (exposure - target) * deltas[sym]))
            fairs[sym] = fair
            out[sym] = self.revert(sym, state.position.get(sym, 0), self.LIMITS[sym], fair)
        if self.debug is not None:
            self.debug.append({
                "t": state.timestamp, "S": S, "exposure": exposure, "smile": list(smile),
                "x": xs, "mid": mids, "fair": fairs,
                "delta_pos": {sym: state.position.get(sym, 0) * d for sym, d in deltas.items()},
            })
        return out

    def revert(self, sym: str, pos: int, limit: int, fair: float) -> List[Order]:
        """Bet on the price snapping back to fair. One order per job, each at the worst price
        we'd accept: the exchange fills it against every better-priced quote in the book, and
        whatever's left can still fill against this tick's market trades.
          buy  up to the limit at  fair - enter   (clearly cheap: get long)
          sell up to the limit at  fair + enter   (clearly rich: get short)
          close a short at fair - exit, close a long at fair + exit (price has come back)"""
        enter, exit_ = self.p["enter"], self.p["exit"]
        can_buy, can_sell = limit - pos, limit + pos
        close_short = min(can_buy, max(-pos, 0))
        close_long = min(can_sell, max(pos, 0))
        orders = []
        if close_short:
            orders.append(Order(sym, math.floor(fair - exit_), close_short))
        if can_buy > close_short:
            orders.append(Order(sym, math.floor(fair - enter), can_buy - close_short))
        if close_long:
            orders.append(Order(sym, math.ceil(fair + exit_), -close_long))
        if can_sell > close_long:
            orders.append(Order(sym, math.ceil(fair + enter), -(can_sell - close_long)))
        return orders

    @staticmethod
    def fit_parabola(xs: List[float], ys: List[float]) -> Optional[List[float]]:
        """Least-squares y = a + b*x + c*x^2 (solves the 3x3 normal equations with Cramer's rule)."""
        s = [sum(x ** k for x in xs) for k in range(5)]
        t = [sum(y * x ** k for x, y in zip(xs, ys)) for k in range(3)]
        A = [[s[0], s[1], s[2]], [s[1], s[2], s[3]], [s[2], s[3], s[4]]]

        def det(M):
            return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
                    - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
                    + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))

        D = det(A)
        if abs(D) < 1e-12:
            return None
        out = []
        for col in range(3):
            M = [row[:] for row in A]
            for r in range(3):
                M[r][col] = t[r]
            out.append(det(M) / D)
        return out

    # ------------------------------------------------------------------ LYCHEE, fruits, basket
    def join_quotes(self, sym: str, state: TradingState, cap: int, center: int = 0) -> List[Order]:
        """Sit on the best bid and the best ask. Market trades happen at exactly those prices,
        so each one that hits us earns half the spread. Quote sizes shrink as we build a
        position, so it never goes past center +- cap."""
        depth = state.order_depths.get(sym)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return []
        pos = state.position.get(sym, 0)
        orders = []
        if center + cap - pos > 0:
            orders.append(Order(sym, max(depth.buy_orders), center + cap - pos))
        if cap + pos - center > 0:
            orders.append(Order(sym, min(depth.sell_orders), -(cap + pos - center)))
        return orders

    # ------------------------------------------------------------------ math helpers
    @staticmethod
    def mid(depth: Optional[OrderDepth]) -> Optional[float]:
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return None
        return (max(depth.buy_orders) + min(depth.sell_orders)) / 2

    @staticmethod
    def bs_call(S: float, K: float, T: float, vol: float) -> float:
        """Black-Scholes call price (no interest rate); T in days, vol per sqrt(day)."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        d2 = d1 - sd
        return S * 0.5 * (1 + math.erf(d1 / math.sqrt(2))) - K * 0.5 * (1 + math.erf(d2 / math.sqrt(2)))

    @staticmethod
    def bs_delta(S: float, K: float, T: float, vol: float) -> float:
        """How many coins the call moves per coin LYCHEE moves."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        return 0.5 * (1 + math.erf(d1 / math.sqrt(2)))

    @staticmethod
    def bs_vega(S: float, K: float, T: float, vol: float) -> float:
        """How many coins the call moves per unit of vol."""
        sd = vol * math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sd * sd) / sd
        return S * math.sqrt(T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)

    @classmethod
    def implied_vol(cls, price: float, S: float, K: float, T: float, guess: float) -> Optional[float]:
        """The vol that makes Black-Scholes match `price` (Newton's method from `guess`)."""
        if price <= max(S - K, 0) + 0.01 or price >= S:
            return None
        vol = guess
        for _ in range(20):
            diff = cls.bs_call(S, K, T, vol) - price
            if abs(diff) < 1e-4:
                return vol
            vega = cls.bs_vega(S, K, T, vol)
            if vega < 1e-6:
                return None
            vol = min(max(vol - diff / vega, 1e-4), 0.5)
        return vol if abs(cls.bs_call(S, K, T, vol) - price) < 0.05 else None


# ============================================================================
# strategies/pearls.py
# SEPEHR's products: WHITE_PEARLS, BLACK_PEARLS, GOLDEN_PEARLS, PINK_PEARLS, BLUE_PEARLS.
#
# Owner: Sepehr. Only Sepehr edits this file.
# Rule for build.py: keep ALL your code inside the class (no top-level functions or
# variables), so nothing clashes with the other strategy files once they're pasted together.
#
# Sepehr2 (Oct 31): Sepehr's version (origin/sepehr 976811a) plus one strategy per pearl, each built
# on a pattern that shows up on all three days:
#   PINK    the five pearls always add up to 50,000, and PINK is the one that moves to close any gap
#   BLUE    a sawtooth: creeps up, then about every 1,000 ticks drops ~45 within 30-50 ticks
#   GOLDEN  sits flat on a level (8000, 7900, 7800, 7750) and slides to the next one now and then
#   BLACK   random walk: just sit on the best bid/ask holding at most 1, so we trade every product
#   WHITE   random walk: Sepehr's own quoting, unchanged
# Local backtest, days -2/-1/0: 7,034 (Sepehr) -> about 65K. Tests (half-days, 3-way rotation,
# mirrored prices, PINK's sum shifted, GOLDEN stepping, and "wrong world" days where BLUE/PINK/GOLDEN
# lose their pattern): analysis/sepehr2/SEPEHR2_TEST.md.
# ============================================================================
class PearlStrategy:
    PEARLS = ("WHITE_PEARLS", "BLACK_PEARLS", "GOLDEN_PEARLS", "PINK_PEARLS", "BLUE_PEARLS")
    LIMITS = {p: 20 for p in PEARLS}

    # ---- WHITE: Sepehr's settings, unchanged (his global knobs are folded in) ----
    WHITE = dict(cap=5, size=5, edge=1, skew=.25, alpha=.15, mode='make')
    THRESHOLD = 4.0
    PRICE_SHIFT = 0.0
    INVENTORY_SKEW = 1.0
    QUOTE_EDGE = 0.0
    INVENTORY_CAP = 2.0
    EXIT_BIAS = 0.0

    # ---- BLACK ----
    BLACK_CAP = 1          # caps 1-3 tested; 1 has the smallest swings (no edge to earn here)

    # ---- PINK ----
    PINK_SUM = 50_000      # the five mids add up to 50,000 (sd ~5) on every day
    PINK_SUM_WINDOW = 5000 # follow the sum slowly in case the scoring day's total is a bit different
    PINK_W = 0.5           # PINK closes ~70% of the gap in 50 ticks, so price it halfway there
    PINK_TAKE = 1          # take any quote at least 1 past fair
    PINK_MAKE = 1          # rest the rest on the best bid/ask, never closer than 1 to fair

    # ---- BLUE ----
    BLUE_N = 10            # a drop = BLUE falling 12+ within 10 ticks
    BLUE_TRIG = 12
    BLUE_QUIET = 10        # the drop is over after 10 ticks without a new low (or a 10-coin bounce)
    BLUE_BOUNCE = 10
    BLUE_DRIFT_POS = 20    # between drops, hold the full limit in the direction BLUE is creeping
    BLUE_MIN_SLOPE = 0.02  # ...but only once the measured creep is at least 0.02 per tick
    BLUE_SLOPE_WINDOW = 3000

    # ---- GOLDEN ----
    GOLDEN_GUARD = 3       # mid more than 3 from the level = a slide has started
    GOLDEN_QUIET = 6       # the slide is over after 6 ticks without a new extreme
    GOLDEN_FAST = 20       # the level = 20-tick EMA of mid while it's flat
    GOLDEN_CAP = 5         # position cap while flat

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        tops = {p: self._top(state.order_depths.get(p)) for p in self.PEARLS}
        for product, strategy in (("WHITE_PEARLS", self.white), ("BLACK_PEARLS", self.black),
                                  ("GOLDEN_PEARLS", self.golden), ("PINK_PEARLS", self.pink),
                                  ("BLUE_PEARLS", self.blue)):
            if tops[product] is None:
                continue
            orders = strategy(product, tops[product], state, mem.setdefault(product, {}), tops)
            if orders:
                result[product] = orders
        return result

    # ------------------------------------------------------------------ helpers
    def _top(self, depth):
        """Best bid, best ask, mid. None if a side is empty or the book is crossed."""
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return None
        bid, ask = max(depth.buy_orders), min(depth.sell_orders)
        if bid >= ask:
            return None
        return bid, ask, (bid + ask) / 2

    def _take_make(self, P, depth, pos, cap, fair, take, make) -> List[Order]:
        """Take every quote at least `take` past fair (up to the limit), then rest whatever room
        is left under `cap` on the best bid/ask, never closer than `make` to fair."""
        limit = self.LIMITS[P]
        orders: List[Order] = []
        buy_room, sell_room = limit - pos, limit + pos
        for price in sorted(depth.sell_orders):
            if price > fair - take or buy_room <= 0:
                break
            q = min(-depth.sell_orders[price], buy_room)
            orders.append(Order(P, price, q))
            buy_room -= q
        for price in sorted(depth.buy_orders, reverse=True):
            if price < fair + take or sell_room <= 0:
                break
            q = min(depth.buy_orders[price], sell_room)
            orders.append(Order(P, price, -q))
            sell_room -= q
        bought, sold = (limit - pos) - buy_room, (limit + pos) - sell_room
        rest_buy = max(0, min(buy_room, cap - pos - bought))
        rest_sell = max(0, min(sell_room, cap + pos - sold))
        bid = min(max(depth.buy_orders), math.floor(fair - make))
        ask = max(min(depth.sell_orders), math.ceil(fair + make))
        if rest_buy > 0:
            orders.append(Order(P, bid, rest_buy))
        if rest_sell > 0:
            orders.append(Order(P, ask, -rest_sell))
        return orders

    def _move_to(self, P, depth, pos, target, urgent) -> List[Order]:
        """Orders that move our position to `target`: buy/sell at the best price on the other
        side if urgent, otherwise rest on our own side of the book."""
        out: List[Order] = []
        bid, ask = max(depth.buy_orders), min(depth.sell_orders)
        limit = self.LIMITS[P]
        need = max(-limit, min(limit, target)) - pos
        if need > 0:
            if urgent:
                q = min(-depth.sell_orders[ask], need)
                out.append(Order(P, ask, q))
                need -= q
            if need > 0:
                out.append(Order(P, bid, need))
        elif need < 0:
            need = -need
            if urgent:
                q = min(depth.buy_orders[bid], need)
                out.append(Order(P, bid, -q))
                need -= q
            if need > 0:
                out.append(Order(P, ask, -need))
        return out

    # ------------------------------------------------------------------ PINK
    def pink(self, P, top, state, rec, tops) -> List[Order]:
        """Fair = (sum target) - (the other four mids). PINK drifts toward it (24% of the gap in
        10 ticks, 70% in 50, 90% in 100), so buy it cheap and sell it rich against that fair."""
        bid, ask, mid = top
        others = [tops[q] for q in self.PEARLS if q != P]
        if any(t is None for t in others):
            return []
        other_sum = sum(t[2] for t in others)
        target = rec.get("tgt", float(self.PINK_SUM))
        target += 2 / (self.PINK_SUM_WINDOW + 1) * (other_sum + mid - target)
        rec["tgt"] = round(target, 3)
        pos = state.position.get(P, 0)
        fair = mid + self.PINK_W * ((target - other_sum) - mid)
        return self._take_make(P, state.order_depths[P], pos, self.LIMITS[P], fair,
                               self.PINK_TAKE, self.PINK_MAKE)

    # ------------------------------------------------------------------ BLUE
    def blue(self, P, top, state, rec, tops) -> List[Order]:
        """Sawtooth. When a sharp move starts (either direction), ride it at the full limit until
        it stops. Otherwise hold the full limit in the direction of the slow creep, measured
        live (an EMA of tick moves outside the sharp moves). Positions change by taking the best
        quote: resting passively to get out after a drop was much worse in every test."""
        bid, ask, mid = top
        hist = rec.setdefault("h", [])
        hist.append(mid)
        del hist[:-(self.BLUE_N + 1)]
        move = mid - hist[0]
        ev, ext, quiet = rec.get("ev", 0), rec.get("x", mid), rec.get("q", 0)
        if ev == 0 and abs(move) >= self.BLUE_TRIG and len(hist) > self.BLUE_N:
            ev, ext, quiet = (1 if move > 0 else -1), mid, 0      # a sharp move just started
        elif ev:
            if (mid - ext) * ev > 0:
                ext, quiet = mid, 0                                # still going: new extreme
            else:
                quiet += 1
            if quiet >= self.BLUE_QUIET or (ext - mid) * ev >= self.BLUE_BOUNCE:
                ev = 0                                             # it's over
        prev = rec.get("pm", mid)
        slope = rec.get("sl", 0.0)
        if ev == 0 and abs(move) < self.BLUE_TRIG:
            slope += 2 / (self.BLUE_SLOPE_WINDOW + 1) * ((mid - prev) - slope)
        rec.update(ev=ev, x=ext, q=quiet, pm=mid, sl=round(slope, 5))

        pos = state.position.get(P, 0)
        depth = state.order_depths[P]
        if ev:
            return self._move_to(P, depth, pos, ev * self.LIMITS[P], True)
        if slope > self.BLUE_MIN_SLOPE:
            target = self.BLUE_DRIFT_POS
        elif slope < -self.BLUE_MIN_SLOPE:
            target = -self.BLUE_DRIFT_POS
        else:
            target = 0
        return self._move_to(P, depth, pos, target, pos * target < 0)

    # ------------------------------------------------------------------ GOLDEN
    def golden(self, P, top, state, rec, tops) -> List[Order]:
        """Flat levels: take/quote 1 around the level (the book never quotes through it).
        When mid leaves the level, a slide has started: ride it at the full limit until it
        makes no new extreme for a few ticks, then the new mid is the new level."""
        bid, ask, mid = top
        level = rec.get("lv", mid)
        ev, ext, quiet = rec.get("ev", 0), rec.get("x", mid), rec.get("q", 0)
        if ev == 0:
            if abs(mid - level) > self.GOLDEN_GUARD:
                ev, ext, quiet = (1 if mid > level else -1), mid, 0
            else:
                level += 2 / (self.GOLDEN_FAST + 1) * (mid - level)
        else:
            if (mid - ext) * ev > 0:
                ext, quiet = mid, 0
            else:
                quiet += 1
            if quiet >= self.GOLDEN_QUIET:
                ev, level = 0, mid
        rec.update(lv=round(level, 3), ev=ev, x=ext, q=quiet)

        pos = state.position.get(P, 0)
        depth = state.order_depths[P]
        if ev:
            return self._move_to(P, depth, pos, ev * self.LIMITS[P], True)
        if abs(pos) > self.GOLDEN_CAP:
            return self._move_to(P, depth, pos, 0, True)           # just finished a slide: get flat
        return self._take_make(P, depth, pos, self.GOLDEN_CAP, round(level), 1, 1)

    # ------------------------------------------------------------------ BLACK
    def black(self, P, top, state, rec, tops) -> List[Order]:
        """Sit on the best bid and ask, never holding more than BLACK_CAP."""
        bid, ask, mid = top
        pos = state.position.get(P, 0)
        out: List[Order] = []
        if self.BLACK_CAP - pos > 0:
            out.append(Order(P, bid, self.BLACK_CAP - pos))
        if self.BLACK_CAP + pos > 0:
            out.append(Order(P, ask, -(self.BLACK_CAP + pos)))
        return out

    # ------------------------------------------------------------------ WHITE (Sepehr's)
    def white(self, product, top, state, rec, tops) -> List[Order]:
        """Sepehr's quoting, unchanged: quote around mid skewed by position, with a momentum
        filter (no buying into a 5-tick fall of more than THRESHOLD, no selling into a rise)."""
        p = self.WHITE
        depth = state.order_depths.get(product)
        bid = max(depth.buy_orders)
        ask = min(depth.sell_orders)
        mid = (bid + ask) / 2
        prev = rec.get('mid', mid)
        ema = rec.get('ema', mid) + p['alpha'] * (mid - rec.get('ema', mid))
        movement = abs(mid - prev)
        vol = rec.get('vol', movement) + .05 * (movement - rec.get('vol', movement))
        rec.update(mid=mid, ema=ema, vol=vol)
        history = rec.setdefault('history', [])
        history.append(mid)
        if len(history) > 21:
            del history[:-21]
        pos = state.position.get(product, 0)
        cool = max(0, rec.get('cool', 0) - 1)
        if p['mode'] == 'stable' and abs(mid - ema) > max(5, 4 * vol):
            cool = 15
        elif p['mode'] == 'guard' and abs(mid - ema) > max(10, 5 * vol):
            cool = 10
        rec['cool'] = cool
        mom = mid - history[-6] if len(history) > 5 else 0.
        cap = min(20, max(1, round(p['cap'] * self.INVENTORY_CAP)))
        reservation = (mid - p['skew'] * self.INVENTORY_SKEW * pos
                       + self.PRICE_SHIFT * max(-8, min(8, mom)))
        edge = p['edge'] + self.QUOTE_EDGE
        buy_price = min(bid, math.floor(reservation - edge), ask - 1)
        sell_price = max(ask, math.ceil(reservation + edge), bid + 1)
        if pos < 0:
            buy_price = min(ask - 1, buy_price + int(self.EXIT_BIAS))
        if pos > 0:
            sell_price = max(bid + 1, sell_price - int(self.EXIT_BIAS))
        buy_qty = max(0, min(p['size'], cap - pos, 20 - pos))
        sell_qty = max(0, min(p['size'], cap + pos, 20 + pos))
        allow_buy = mom >= -self.THRESHOLD
        allow_sell = mom <= self.THRESHOLD
        orders = []
        if buy_qty and allow_buy and (cool == 0 or pos < 0):
            orders.append(Order(product, int(buy_price), int(buy_qty)))
        if sell_qty and allow_sell and (cool == 0 or pos > 0):
            orders.append(Order(product, int(sell_price), -int(sell_qty)))
        return orders


# ============================================================================
# trader.py
# The Trader class UTEFA calls every tick. It doesn't make trading decisions itself:
# it asks each strategy class for its orders, makes sure no order breaks a position
# limit, and hands everything back.
#
# SHARED FILE: don't change it without telling the whole team (it affects everyone).
# ============================================================================
class Trader:
    # name -> strategy class. The name is also that strategy's key in traderData.
    STRATEGIES = {
        "core": CoreStrategy,
        "fruit_lychee": FruitLycheeStrategy,
        "pearls": PearlStrategy,
    }

    def __init__(self, only: Optional[List[str]] = None):
        # `only` is for local testing (backtest.py --only pearls); UTEFA never passes it
        names = only if only else list(self.STRATEGIES)
        self.strategies = {name: self.STRATEGIES[name]() for name in names}

    def run(self, state: TradingState):
        # Each strategy gets its own slot in traderData so nobody overwrites anyone else
        mem = json.loads(state.traderData) if state.traderData else {}
        result: Dict[str, List[Order]] = {}

        for name, strategy in self.strategies.items():
            try:
                orders = strategy.trade(state, mem.setdefault(name, {}))
            except Exception as e:
                # One strategy crashing only costs its own products this tick
                print(f"[{name}] crashed at t={state.timestamp}: {e!r}")
                continue
            for product, product_orders in orders.items():
                limit = strategy.LIMITS.get(product)
                if limit is not None:
                    product_orders = self.clip_to_limit(
                        product_orders, state.position.get(product, 0), limit
                    )
                result[product] = product_orders

        return result, 0, json.dumps(mem, separators=(",", ":"))

    @staticmethod
    def clip_to_limit(orders: List[Order], position: int, limit: int) -> List[Order]:
        """Shrink orders so that even if every buy (or every sell) filled, we'd stay
        within the limit. Otherwise the exchange cancels them."""
        can_buy, can_sell = limit - position, limit + position
        clipped: List[Order] = []
        for o in orders:
            if o.quantity > 0:
                qty = max(0, min(o.quantity, can_buy))
                can_buy -= qty
            else:
                qty = -max(0, min(-o.quantity, can_sell))
                can_sell += qty
            if qty != 0:
                clipped.append(Order(o.symbol, o.price, qty))
        return clipped

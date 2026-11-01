"""ALI's products: AMETHYST, TOFFEE_CAKE, PAPER_LANTERNS, TELLURIUM, JELLY, PEANUT_BUTTER.

Owner: Ali. Only Ali edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.

Ali2 (Oct 31): Ali's version with changes that beat it on every stress test we ran:
the 3 days, the 6 half-days, a 3-way rotation (tune on 2 days, test on the 3rd), mirrored
prices, and TOFFEE moved +-25 or jumping +-30 mid-day.
Results and scripts: analysis/ali2/ALI2_TEST.md.
"""
import math
from typing import Dict, List

from datamodel import Order, TradingState


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

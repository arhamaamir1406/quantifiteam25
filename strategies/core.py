"""ALI's products: AMETHYST, TOFFEE_CAKE, PAPER_LANTERNS, TELLURIUM, JELLY, PEANUT_BUTTER.

Owner: Ali. Only Ali edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.
"""
from typing import Dict, List

from datamodel import Order, TradingState
from strategies.common import market_make


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
        depth = state.order_depths.get("AMETHYST")
        if depth is not None:
            position = state.position.get("AMETHYST", 0)
            result["AMETHYST"] = market_make(
                "AMETHYST", depth, position, self.LIMITS["AMETHYST"], fair=10_000
            )

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

    # =====================================================================
    # TOFFEE_CAKE: mean-reverting around ~5,000 (reversion strongest at 500 ticks)
    # =====================================================================
    def toffee_cake(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "TOFFEE_CAKE"
        EMA_WINDOW = 500   # Step 2: reversion strongest at 500 ticks
        EDGE = 6           # Step 4: trades happen ~7.5 from mid
        TAKE = 8           # take any quote at least this far past fair
        SIZE = 10
        SKEW = 0.1

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        book = state.order_depths[P]
        pos = state.position.get(P, 0)
        limit = self.LIMITS[P]

        # 1. fair value: slow EMA
        fair = mem.get("toffee_ema", mid)
        fair += 2 / (EMA_WINDOW + 1) * (mid - fair)
        mem["toffee_ema"] = fair

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
        FAST = 20          # smooths the flicker (bounce -0.5)
        SLOW = 100         # lags behind on trends
        EDGE = 1           # spread ~4, trades ~2 from mid
        SIZE = 15
        TREND_GAIN = 10    # target position = gain * trend
        CHASE = 15         # take if this far from target
        SKEW = 0.1

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        book = state.order_depths[P]
        pos = state.position.get(P, 0)
        limit = self.LIMITS[P]

        # 1. fast and slow EMAs
        fast = mem.get("pl_fast", mid)
        slow = mem.get("pl_slow", mid)
        fast += 2 / (FAST + 1) * (mid - fast)
        slow += 2 / (SLOW + 1) * (mid - slow)
        mem["pl_fast"] = fast
        mem["pl_slow"] = slow

        # 2-4. trend, fair value, target position
        trend = fast - slow
        fair = fast + 0.25 * trend
        target = max(-limit, min(limit, round(TREND_GAIN * trend)))

        orders: List[Order] = []
        buy_room = limit - pos
        sell_room = limit + pos

        # 5. chase the trend if far from target
        if target - pos > CHASE and buy_room > 0:
            qty = min(target - pos, buy_room, -book.sell_orders[best_ask])
            orders.append(Order(P, best_ask, qty))
            buy_room -= qty
        elif pos - target > CHASE and sell_room > 0:
            qty = min(pos - target, sell_room, book.buy_orders[best_bid])
            orders.append(Order(P, best_bid, -qty))
            sell_room -= qty

        # 6. quote around fair, skewed toward target (skew uses pos - target)
        orders += self._quote(P, best_bid, best_ask, pos - target, fair, EDGE, SIZE,
                              limit + abs(target), SKEW, buy_room, sell_room)
        return {P: orders}

    # =====================================================================
    # TELLURIUM: jumps; trade flow predicts the next move (adverse selection)
    # =====================================================================
    def tellurium(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "TELLURIUM"
        FLOW_WINDOW = 10   # EMA of recent trade direction
        FLOW_GAIN = 1.0    # how far to shift fair per unit of net flow
        EDGE = 4           # half-spread ~4.5
        SIZE = 3           # small: every fill is risky
        CAP = 10           # Step 5: 100-tick moves up to ~380
        SKEW = 0.4
        JUMP = 15          # mid move bigger than this = a jump (avg tick move is 1.3)
        COOLDOWN = 20      # ticks to only reduce position after a jump

        top = self._mid(state.order_depths.get(P))
        if top is None:
            return {}
        best_bid, best_ask, mid = top
        pos = state.position.get(P, 0)
        prev_mid = mem.get("tel_mid", mid)

        # 1. trade flow: did recent trades happen above mid (buyers) or below (sellers)?
        flow_now = 0
        for t in (state.market_trades or {}).get(P, []):
            if t.price > prev_mid:
                flow_now += t.quantity
            elif t.price < prev_mid:
                flow_now -= t.quantity
        flow = mem.get("tel_flow", 0.0)
        flow += 2 / (FLOW_WINDOW + 1) * (flow_now - flow)
        mem["tel_flow"] = flow

        # 2. jump guard
        cool = mem.get("tel_cool", 0)
        cool = COOLDOWN if abs(mid - prev_mid) > JUMP else max(0, cool - 1)
        mem["tel_cool"] = cool
        mem["tel_mid"] = mid

        # 3. fair = mid shifted toward where the flow says price is going
        fair = mid + FLOW_GAIN * flow

        orders = self._quote(P, best_bid, best_ask, pos, fair, EDGE, SIZE, CAP, SKEW)

        # 4. right after a jump, only keep orders that shrink our position
        if cool > 0:
            orders = [o for o in orders
                      if (o.quantity > 0 and pos < 0) or (o.quantity < 0 and pos > 0)]
        return {P: orders}

    # =====================================================================
    # JELLY: random walk around ~2,000, medium risk
    # =====================================================================
    def jelly(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        P = "JELLY"
        EMA_WINDOW = 50
        EDGE = 4           # trades ~5.5 from mid
        SIZE = 5
        CAP = 25           # Step 5: 100-tick moves up to ~150
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
        EDGE = 2           # trades ~3 from mid
        SIZE = 3
        CAP = 15           # Step 5: 100-tick moves up to ~170
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
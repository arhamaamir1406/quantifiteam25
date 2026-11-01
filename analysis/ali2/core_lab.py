"""LAB copy of Ali's CoreStrategy for testing variants side by side (not team code).

CORE_PARAMS env var = {"TOFFEE_CAKE": {"kind": ..., ...}, ...}. A product that isn't listed (or
lists no kind) runs Ali's original code with Ali's original numbers.
"""
import json, math, os
from typing import Dict, List

from datamodel import Order, TradingState
from strategies.common import market_make


class CoreStrategy:
    LIMITS = {"AMETHYST": 50, "TOFFEE_CAKE": 50, "PAPER_LANTERNS": 50, "TELLURIUM": 40,
              "JELLY": 50, "PEANUT_BUTTER": 50}
    DEFAULTS = {  # Ali's original numbers
        "AMETHYST": {"kind": "ali"},
        "TOFFEE_CAKE": {"kind": "ali", "mode": "ema", "win": 500, "home": 5000, "edge": 6, "take": 8,
                        "size": 10, "skew": 0.1},
        "PAPER_LANTERNS": {"kind": "ali", "fast": 20, "slow": 100, "edge": 1, "size": 15, "gain": 10,
                           "chase": 15, "skew": 0.1, "fk": 0.25},
        "TELLURIUM": {"kind": "ali", "fw": 10, "fg": 1.0, "edge": 4, "size": 3, "cap": 10, "skew": 0.4,
                      "jump": 15, "cool": 20},
        "JELLY": {"kind": "ali", "win": 50, "edge": 4, "size": 5, "cap": 25, "skew": 0.2},
        "PEANUT_BUTTER": {"kind": "ali", "win": 20, "edge": 2, "size": 3, "cap": 15, "skew": 0.3},
    }

    def __init__(self):
        cfg = json.loads(os.environ.get("CORE_PARAMS", "{}"))
        self.cfg = {p: {**d, **cfg.get(p, {})} for p, d in self.DEFAULTS.items()}

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        for P, fn in (("AMETHYST", self.amethyst), ("TOFFEE_CAKE", self.toffee_cake),
                      ("PAPER_LANTERNS", self.paper_lanterns), ("TELLURIUM", self.tellurium),
                      ("JELLY", self.random_walk), ("PEANUT_BUTTER", self.random_walk)):
            if P in state.order_depths:
                out = fn(P, state, mem, self.cfg[P])
                if out:
                    result[P] = out
        return result

    # ------------------------------------------------------------------ shared helpers
    def _mid(self, book):
        if book is None or not book.buy_orders or not book.sell_orders:
            return None
        best_bid = max(book.buy_orders)
        best_ask = min(book.sell_orders)
        return best_bid, best_ask, (best_bid + best_ask) / 2

    def _quote(self, P, best_bid, best_ask, pos, fair, edge, size, cap, skew,
               buy_room=None, sell_room=None) -> List[Order]:
        """Ali's resting bid/ask around fair, skewed by position, never above cap."""
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

    @staticmethod
    def _join(P, book, pos, cap) -> List[Order]:
        """Sit on the best bid and best ask, never holding more than +-cap."""
        o = []
        if cap - pos > 0:
            o.append(Order(P, max(book.buy_orders), cap - pos))
        if cap + pos > 0:
            o.append(Order(P, min(book.sell_orders), -(cap + pos)))
        return o

    @staticmethod
    def _around(P, book, pos, lim, fair, take, make) -> List[Order]:
        """Take every quote at least `take` past fair, then rest the rest of the room at the best
        bid/ask (or no closer than `make` to fair)."""
        o, cb, cs = [], lim - pos, lim + pos
        for p in sorted(book.sell_orders):
            if p > fair - take or cb <= 0:
                break
            q = min(-book.sell_orders[p], cb); o.append(Order(P, p, q)); cb -= q
        for p in sorted(book.buy_orders, reverse=True):
            if p < fair + take or cs <= 0:
                break
            q = min(book.buy_orders[p], cs); o.append(Order(P, p, -q)); cs -= q
        bid = min(max(book.buy_orders), math.floor(fair - make))
        ask = max(min(book.sell_orders), math.ceil(fair + make))
        if cb > 0:
            o.append(Order(P, bid, cb))
        if cs > 0:
            o.append(Order(P, ask, -cs))
        return o

    # ------------------------------------------------------------------ products
    def amethyst(self, P, state, mem, c):
        book, pos = state.order_depths[P], state.position.get(P, 0)
        if not book.buy_orders or not book.sell_orders:
            return []
        if c["kind"] == "join":
            return self._join(P, book, pos, c.get("cap", 50))
        if c["kind"] == "around":
            return self._around(P, book, pos, 50, 10000, c["take"], c["make"])
        return market_make(P, book, pos, 50, fair=10_000)

    def toffee_cake(self, P, state, mem, c):
        top = self._mid(state.order_depths.get(P))
        if top is None:
            return []
        best_bid, best_ask, mid = top
        book, pos, limit = state.order_depths[P], state.position.get(P, 0), 50
        if c["mode"] == "fixed":
            fair = c["home"]
        else:  # "ema": Ali's (starts at the first price seen); "hybrid": starts at home
            key = "toffee_ema" if c["mode"] == "ema" else "toffee_h"
            fair = mem.get(key, mid if c["mode"] == "ema" else c["home"])
            fair += 2 / (c["win"] + 1) * (mid - fair)
            mem[key] = fair
        if c["kind"] == "around":
            return self._around(P, book, pos, limit, fair, c["take"], c["make"])
        orders, buy_room, sell_room = [], limit - pos, limit + pos
        for price in sorted(book.sell_orders):
            if price <= fair - c["take"] and buy_room > 0:
                qty = min(-book.sell_orders[price], buy_room)
                orders.append(Order(P, price, qty)); buy_room -= qty
        for price in sorted(book.buy_orders, reverse=True):
            if price >= fair + c["take"] and sell_room > 0:
                qty = min(book.buy_orders[price], sell_room)
                orders.append(Order(P, price, -qty)); sell_room -= qty
        orders += self._quote(P, best_bid, best_ask, pos, fair, c["edge"], c["size"], limit, c["skew"],
                              buy_room, sell_room)
        return orders

    def paper_lanterns(self, P, state, mem, c):
        top = self._mid(state.order_depths.get(P))
        if top is None:
            return []
        best_bid, best_ask, mid = top
        book, pos, limit = state.order_depths[P], state.position.get(P, 0), 50
        if c["kind"] == "momo":
            # fair = smoothed price + k x (how much the smoothed price rose over the last `look` ticks).
            # History is sampled every `step` ticks so traderData stays small.
            ema = mem.get("pl_ema", mid)
            ema += 2 / (c.get("n", 20) + 1) * (mid - ema)
            mem["pl_ema"] = ema
            i = mem.get("pl_i", 0)
            hist = mem.setdefault("pl_hist", [])
            step = c.get("step", 10)
            if i % step == 0:
                hist.append(round(ema, 3))
                del hist[:-(c.get("look", 200) // step + 1)]
            mem["pl_i"] = i + 1
            full = len(hist) == c.get("look", 200) // step + 1
            mom = ema - hist[0] if full else 0.0
            return self._around(P, book, pos, limit, ema + c.get("k", 0.75) * mom, c.get("take", 2), c.get("make", 1))
        fast = mem.get("pl_fast", mid)
        slow = mem.get("pl_slow", mid)
        fast += 2 / (c["fast"] + 1) * (mid - fast)
        slow += 2 / (c["slow"] + 1) * (mid - slow)
        mem["pl_fast"], mem["pl_slow"] = fast, slow
        trend = fast - slow
        fair = fast + c["fk"] * trend
        target = max(-limit, min(limit, round(c["gain"] * trend)))
        orders, buy_room, sell_room = [], limit - pos, limit + pos
        if target - pos > c["chase"] and buy_room > 0:
            qty = min(target - pos, buy_room, -book.sell_orders[best_ask])
            orders.append(Order(P, best_ask, qty)); buy_room -= qty
        elif pos - target > c["chase"] and sell_room > 0:
            qty = min(pos - target, sell_room, book.buy_orders[best_bid])
            orders.append(Order(P, best_bid, -qty)); sell_room -= qty
        orders += self._quote(P, best_bid, best_ask, pos - target, fair, c["edge"], c["size"],
                              limit + abs(target), c["skew"], buy_room, sell_room)
        return orders

    def tellurium(self, P, state, mem, c):
        top = self._mid(state.order_depths.get(P))
        if top is None:
            return []
        best_bid, best_ask, mid = top
        pos = state.position.get(P, 0)
        if c["kind"] == "join":
            return self._join(P, state.order_depths[P], pos, c["cap"])
        prev_mid = mem.get("tel_mid", mid)
        flow_now = 0
        for t in (state.market_trades or {}).get(P, []):
            if t.price > prev_mid:
                flow_now += t.quantity
            elif t.price < prev_mid:
                flow_now -= t.quantity
        flow = mem.get("tel_flow", 0.0)
        flow += 2 / (c["fw"] + 1) * (flow_now - flow)
        mem["tel_flow"] = flow
        cool = mem.get("tel_cool", 0)
        cool = c["cool"] if abs(mid - prev_mid) > c["jump"] else max(0, cool - 1)
        mem["tel_cool"], mem["tel_mid"] = cool, mid
        fair = mid + c["fg"] * flow
        orders = self._quote(P, best_bid, best_ask, pos, fair, c["edge"], c["size"], c["cap"], c["skew"])
        if cool > 0:
            orders = [o for o in orders if (o.quantity > 0 and pos < 0) or (o.quantity < 0 and pos > 0)]
        return orders

    def random_walk(self, P, state, mem, c):
        """JELLY and PEANUT_BUTTER."""
        top = self._mid(state.order_depths.get(P))
        if top is None or c["kind"] == "off":
            return []
        best_bid, best_ask, mid = top
        pos = state.position.get(P, 0)
        if c["kind"] == "join":
            return self._join(P, state.order_depths[P], pos, c["cap"])
        key = "jelly_ema" if P == "JELLY" else "pb_ema"
        fair = mem.get(key, mid)
        fair += 2 / (c["win"] + 1) * (mid - fair)
        mem[key] = fair
        return self._quote(P, best_bid, best_ask, pos, fair, c["edge"], c["size"], c["cap"], c["skew"])

"""SEPEHR's products: WHITE_PEARLS, BLACK_PEARLS, GOLDEN_PEARLS, PINK_PEARLS, BLUE_PEARLS.

Owner: Sepehr. Only Sepehr edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.

Sepehr2 (Oct 31): Sepehr's version (origin/sepehr 976811a) plus one strategy per pearl, each built
on a pattern that shows up on all three days:
  PINK    the five pearls always add up to 50,000, and PINK is the one that moves to close any gap
  BLUE    a sawtooth: creeps up, then about every 1,000 ticks drops ~45 within 30-50 ticks
  GOLDEN  sits flat on a level (8000, 7900, 7800, 7750) and slides to the next one now and then
  BLACK   random walk: just sit on the best bid/ask holding at most 1, so we trade every product
  WHITE   random walk: Sepehr's own quoting, unchanged
Local backtest, days -2/-1/0: 7,034 (Sepehr) -> about 65K. Tests (half-days, 3-way rotation,
mirrored prices, PINK's sum shifted, GOLDEN stepping, and "wrong world" days where BLUE/PINK/GOLDEN
lose their pattern): analysis/sepehr2/SEPEHR2_TEST.md.
"""
import math
from typing import Dict, List

from datamodel import Order, TradingState


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

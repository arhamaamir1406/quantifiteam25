"""Pearls LAB version (scratch only, never goes in the repo).

Every product picks a 'kind' of strategy; the DEFAULTS reproduce Sepehr's pushed pearls.py
(origin/sepehr 976811a) exactly. The env var PEARL_PARAMS = {"PRODUCT": {overrides}} switches
any product to a variant, so one backtest can test a different variant for each pearl at once
(the pearls never share positions; only PINK's 'sum' kind *reads* the other pearls' books).

kinds:
  sepehr  Sepehr's code, verbatim (mode make/guard/stable, momentum filter, cooldown)
  off     no orders
  join    sit on the best bid/ask, never holding more than +-cap
  sum     PINK only: fair = TARGET - (sum of the other four mids), TARGET = 50,000 or a slow
          EMA of the five-pearl sum that starts at 50,000; then take/make around fair
  level   GOLDEN only: fair = a fast EMA of mid (the plateau level); take/make around it, but
          after a big move away from a slow EMA (a step down/up in progress) only reduce position
  momo    fair = EMA(mid) + k x (EMA rise over `look` ticks); take/make around it
"""
import json
import math
import os
from typing import Dict, List

from datamodel import Order, TradingState


class PearlStrategy:
    PEARLS = ("WHITE_PEARLS", "BLACK_PEARLS", "GOLDEN_PEARLS", "PINK_PEARLS", "BLUE_PEARLS")
    LIMITS = {p: 20 for p in PEARLS}

    # Sepehr's PARAMS + globals (THRESHOLD 4, PRICE_SHIFT 0, INVENTORY_SKEW 1, QUOTE_EDGE 0,
    # INVENTORY_CAP 2, EXIT_BIAS 0), expressed per product
    DEFAULTS = {
        "WHITE_PEARLS": dict(kind="sepehr", cap=5, size=5, edge=1, skew=.25, alpha=.15, mode="make"),
        "BLACK_PEARLS": dict(kind="sepehr", cap=0, size=0, edge=2, skew=.5, alpha=.20, mode="guard"),
        "GOLDEN_PEARLS": dict(kind="sepehr", cap=3, size=3, edge=1, skew=.35, alpha=.30, mode="stable"),
        "PINK_PEARLS": dict(kind="sepehr", cap=5, size=1, edge=1, skew=.20, alpha=.15, mode="make"),
        "BLUE_PEARLS": dict(kind="sepehr", cap=0, size=0, edge=2, skew=.5, alpha=.25, mode="guard"),
    }
    SEP_GLOBALS = dict(threshold=4.0, price_shift=0.0, inv_skew=1.0, quote_edge=0.0, inv_cap=2.0, exit_bias=0.0)

    def __init__(self):
        over = json.loads(os.environ.get("PEARL_PARAMS", "{}") or "{}")
        self.P = {}
        for p in self.PEARLS:
            o = over.get(p, {})
            base = self.DEFAULTS[p] if o.get("kind", "sepehr") == "sepehr" else {}  # new kinds start clean
            self.P[p] = {**self.SEP_GLOBALS, **base, **o}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _top(depth):
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return None
        bid, ask = max(depth.buy_orders), min(depth.sell_orders)
        if bid >= ask:
            return None
        return bid, ask, (bid + ask) / 2

    @staticmethod
    def _take_make(P, depth, pos, limit, cap, fair, take, make, size=None) -> List[Order]:
        """Take every quote at least `take` past fair (up to the limit), then rest the room left
        under `cap` on the best bid/ask, never closer than `make` to fair."""
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
        pb = max(0, min(buy_room, cap - pos - bought))
        ps = max(0, min(sell_room, cap + pos - sold))
        if size is not None:
            pb, ps = min(pb, size), min(ps, size)
        bid = min(max(depth.buy_orders), math.floor(fair - make))
        ask = max(min(depth.sell_orders), math.ceil(fair + make))
        if pb > 0:
            orders.append(Order(P, bid, pb))
        if ps > 0:
            orders.append(Order(P, ask, -ps))
        return orders

    # ------------------------------------------------------------------ main
    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        tops = {p: self._top(state.order_depths.get(p)) for p in self.PEARLS}
        for prod in self.PEARLS:
            p = self.P[prod]
            top = tops[prod]
            if top is None:
                continue
            fn = getattr(self, "_k_" + p["kind"])
            orders = fn(prod, p, top, state, mem.setdefault(prod, {}), tops)
            if orders:
                result[prod] = orders
        return result

    # ------------------------------------------------------------------ kinds
    def _k_off(self, prod, p, top, state, rec, tops):
        return []

    def _k_join(self, prod, p, top, state, rec, tops):
        bid, ask, _ = top
        pos = state.position.get(prod, 0)
        cap = p["cap"]
        out = []
        if cap - pos > 0:
            out.append(Order(prod, bid, cap - pos))
        if cap + pos > 0:
            out.append(Order(prod, ask, -(cap + pos)))
        return out

    def _k_sum(self, prod, p, top, state, rec, tops):
        bid, ask, mid = top
        others = [tops[q] for q in self.PEARLS if q != prod]
        if any(t is None for t in others):
            return []
        other_sum = sum(t[2] for t in others)
        target = rec.get("tgt", p.get("target", 50000.0))
        w = p.get("tgt_window", 0)
        if w:
            target += 2 / (w + 1) * (other_sum + mid - target)
            rec["tgt"] = round(target, 3)
        pos = state.position.get(prod, 0)
        fair = mid + p.get("w", 1.0) * ((target - other_sum) - mid) - p.get("skew", 0.0) * pos
        return self._take_make(prod, state.order_depths[prod], pos, 20, p.get("cap", 20), fair,
                               p.get("take", 2), p.get("make", 1), p.get("size"))

    def _k_level(self, prod, p, top, state, rec, tops):
        bid, ask, mid = top
        fast = rec.get("f", mid)
        fast += 2 / (p.get("fast", 20) + 1) * (mid - fast)
        slow = rec.get("s", mid)
        slow += 2 / (p.get("slow", 200) + 1) * (mid - slow)
        cool = max(0, rec.get("c", 0) - 1)
        if abs(mid - slow) > p.get("guard", 4):
            cool = p.get("cool", 50)
        rec.update(f=round(fast, 3), s=round(slow, 3), c=cool)
        pos = state.position.get(prod, 0)
        depth = state.order_depths[prod]
        if cool:
            # step in progress: only work our way out, resting on the best bid/ask
            if pos > 0:
                return [Order(prod, ask, -pos)] if p.get("exit_passive", 1) else [Order(prod, bid, -pos)]
            if pos < 0:
                return [Order(prod, bid, -pos)] if p.get("exit_passive", 1) else [Order(prod, ask, -pos)]
            return []
        fair = round(fast) if p.get("round", 1) else fast
        fair -= p.get("skew", 0.0) * pos
        return self._take_make(prod, depth, pos, 20, p.get("cap", 20), fair,
                               p.get("take", 1), p.get("make", 1), p.get("size"))

    def _k_momo(self, prod, p, top, state, rec, tops):
        bid, ask, mid = top
        ema = rec.get("e", mid)
        ema += 2 / (p.get("ema", 10) + 1) * (mid - ema)
        hist = rec.setdefault("h", [])
        hist.append(round(ema, 2))
        look = p.get("look", 10)
        del hist[:-(look + 1)]
        rec["e"] = round(ema, 3)
        trend = ema - hist[0] if len(hist) == look + 1 else 0.0
        pos = state.position.get(prod, 0)
        fair = ema + p.get("k", 1.0) * trend - p.get("skew", 0.0) * pos
        return self._take_make(prod, state.order_depths[prod], pos, 20, p.get("cap", 20), fair,
                               p.get("take", 2), p.get("make", 1), p.get("size"))

    def _move_to(self, prod, depth, pos, target, urgent, slip=0):
        """Orders that move our position toward `target`: cross the spread if urgent
        (up to `slip` past the best price), otherwise rest on the best bid/ask."""
        out: List[Order] = []
        bid, ask = max(depth.buy_orders), min(depth.sell_orders)
        need = max(-20, min(20, target)) - pos
        if need > 0:
            if urgent:
                for price in sorted(depth.sell_orders):
                    if price > ask + slip or need <= 0:
                        break
                    q = min(-depth.sell_orders[price], need)
                    out.append(Order(prod, price, q)); need -= q
            if need > 0:
                out.append(Order(prod, bid, need))
        elif need < 0:
            need = -need
            if urgent:
                for price in sorted(depth.buy_orders, reverse=True):
                    if price < bid - slip or need <= 0:
                        break
                    q = min(depth.buy_orders[price], need)
                    out.append(Order(prod, price, -q)); need -= q
            if need > 0:
                out.append(Order(prod, ask, -need))
        return out

    def _k_saw(self, prod, p, top, state, rec, tops):
        """Ride sharp moves (either direction) and, between them, lean with the measured drift.
        BLUE: drifts up, then every ~1000 ticks drops ~45 over 30-50 ticks."""
        bid, ask, mid = top
        hist = rec.setdefault("h", [])
        hist.append(mid)
        del hist[:-(p.get("n", 5) + 1)]
        move = mid - hist[0]
        ev, ext, quiet = rec.get("ev", 0), rec.get("x", mid), rec.get("q", 0)
        if ev == 0 and abs(move) >= p.get("trig", 8) and len(hist) > p.get("n", 5):
            ev, ext, quiet = (1 if move > 0 else -1), mid, 0
        elif ev:
            if (mid - ext) * ev > 0:
                ext, quiet = mid, 0
            else:
                quiet += 1
            if quiet >= p.get("quiet", 6) or (ext - mid) * ev >= p.get("bounce", 6):
                ev = 0
        # drift: EMA of tick moves outside events
        prev = rec.get("pm", mid)
        slope = rec.get("sl", p.get("slope0", 0.0))
        if ev == 0 and abs(move) < p.get("trig", 8):
            slope += 2 / (p.get("sw", 3000) + 1) * ((mid - prev) - slope)
        rec.update(ev=ev, x=ext, q=quiet, pm=mid, sl=round(slope, 5))
        pos = state.position.get(prod, 0)
        depth = state.order_depths[prod]
        if ev:
            return self._move_to(prod, depth, pos, ev * p.get("ride", 20), True, p.get("slip", 0))
        dp = p.get("drift_pos", 0)
        target = dp if slope > p.get("smin", 0.02) else (-dp if slope < -p.get("smin", 0.02) else 0)
        return self._move_to(prod, depth, pos, target, p.get("exit_take", 0) and pos * target < 0, 0)

    def _k_slide(self, prod, p, top, state, rec, tops):
        """GOLDEN: flat plateaus; ride the slides (either direction) to the next plateau."""
        bid, ask, mid = top
        level = rec.get("lv", mid)
        ev, ext, quiet = rec.get("ev", 0), rec.get("x", mid), rec.get("q", 0)
        if ev == 0:
            if abs(mid - level) > p.get("guard", 3):
                ev, ext, quiet = (1 if mid > level else -1), mid, 0
            else:
                level += 2 / (p.get("fast", 20) + 1) * (mid - level)
        else:
            if (mid - ext) * ev > 0:
                ext, quiet = mid, 0
            else:
                quiet += 1
            if quiet >= p.get("quiet", 6):
                ev, level = 0, mid
        rec.update(lv=round(level, 3), ev=ev, x=ext, q=quiet)
        pos = state.position.get(prod, 0)
        depth = state.order_depths[prod]
        if ev:
            return self._move_to(prod, depth, pos, ev * p.get("ride", 20), True, p.get("slip", 0))
        if p.get("flat_first", 1) and pos != 0 and abs(pos) > p.get("cap", 5):
            return self._move_to(prod, depth, pos, 0, True, 0)
        fair = round(level) - p.get("skew", 0.0) * pos
        return self._take_make(prod, depth, pos, 20, p.get("cap", 5), fair,
                               p.get("take", 1), p.get("make", 1), p.get("size"))

    def _k_sepehr(self, product, p, top, state, rec, tops):
        """Sepehr's loop body, verbatim except the constants come from p."""
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
        if p['cap'] == 0:
            return []
        pos = state.position.get(product, 0)
        cool = max(0, rec.get('cool', 0) - 1)
        if p['mode'] == 'stable' and abs(mid - ema) > max(5, 4 * vol):
            cool = 15
        elif p['mode'] == 'guard' and abs(mid - ema) > max(10, 5 * vol):
            cool = 10
        rec['cool'] = cool
        mom = mid - history[-6] if len(history) > 5 else 0.
        cap = min(20, max(1, round(p['cap'] * p['inv_cap'])))
        reservation = mid - p['skew'] * p['inv_skew'] * pos + p['price_shift'] * max(-8, min(8, mom))
        edge = p['edge'] + p['quote_edge']
        buy_price = min(bid, math.floor(reservation - edge), ask - 1)
        sell_price = max(ask, math.ceil(reservation + edge), bid + 1)
        if pos < 0:
            buy_price = min(ask - 1, buy_price + int(p['exit_bias']))
        if pos > 0:
            sell_price = max(bid + 1, sell_price - int(p['exit_bias']))
        buy_qty = max(0, min(p['size'], cap - pos, 20 - pos))
        sell_qty = max(0, min(p['size'], cap + pos, 20 + pos))
        allow_buy = mom >= -p['threshold']
        allow_sell = mom <= p['threshold']
        orders = []
        if buy_qty and allow_buy and (cool == 0 or pos < 0):
            orders.append(Order(product, int(buy_price), int(buy_qty)))
        if sell_qty and allow_sell and (cool == 0 or pos > 0):
            orders.append(Order(product, int(sell_price), -int(sell_qty)))
        return orders

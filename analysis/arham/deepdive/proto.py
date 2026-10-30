"""Throwaway prototypes to size each Prosperity-style idea on our data. Not team code."""
import math, os
from collections import deque
from datamodel import Order

LIM = {"AMETHYST": 50, "TOFFEE_CAKE": 50, "PAPER_LANTERNS": 50, "TELLURIUM": 40, "JELLY": 50,
       "PEANUT_BUTTER": 50, "WHITE_PEARLS": 20, "BLACK_PEARLS": 20, "GOLDEN_PEARLS": 20,
       "PINK_PEARLS": 20, "BLUE_PEARLS": 20}
PEARLS = ["WHITE_PEARLS", "BLACK_PEARLS", "GOLDEN_PEARLS", "PINK_PEARLS", "BLUE_PEARLS"]
V = int(os.environ.get("V", "0"))

def join(sym, d, pos, cap):
    bb, ba = max(d.buy_orders), min(d.sell_orders); o = []
    if cap - pos > 0: o.append(Order(sym, bb, cap - pos))
    if cap + pos > 0: o.append(Order(sym, ba, -(cap + pos)))
    return o

def around(sym, d, pos, lim, fair, take, make):
    bb, ba = max(d.buy_orders), min(d.sell_orders); o = []; cb, cs = lim - pos, lim + pos
    for p in sorted(d.sell_orders):
        if p > fair - take or cb <= 0: break
        q = min(-d.sell_orders[p], cb); o.append(Order(sym, p, q)); cb -= q
    for p in sorted(d.buy_orders, reverse=True):
        if p < fair + take or cs <= 0: break
        q = min(d.buy_orders[p], cs); o.append(Order(sym, p, -q)); cs -= q
    bid = min(bb, math.floor(fair - make)); ask = max(ba, math.ceil(fair + make))
    if cb > 0: o.append(Order(sym, bid, cb))
    if cs > 0: o.append(Order(sym, ask, -cs))
    return o

class Trader:
    def __init__(self):
        self.ema = None; self.hist = deque(maxlen=201)

    def run(self, state):
        D, P, out = state.order_depths, state.position, {}
        mid = {s: (max(D[s].buy_orders) + min(D[s].sell_orders)) / 2 for s in LIM if s in D}
        pos = lambda s: P.get(s, 0)
        # AMETHYST: 0 = example-style baseline, 1+ = Prosperity resin style (fair 10000, take through it, quote around it)
        s = "AMETHYST"
        out[s] = join(s, D[s], pos(s), 50) if V == 0 else around(s, D[s], pos(s), 50, 10000, 1, 1)
        # TOFFEE_CAKE: anchor 5000 (mean 5002-5004 every day)
        s = "TOFFEE_CAKE"
        out[s] = [join(s, D[s], pos(s), 10), around(s, D[s], pos(s), 50, 5000, 3, 1),
                  around(s, D[s], pos(s), 50, 5000, 8, 4), around(s, D[s], pos(s), 50, 5000, 12, 6)][V]
        # PAPER_LANTERNS: momentum. fair = smoothed mid + k * (its change over 200 ticks)
        s = "PAPER_LANTERNS"; m = mid[s]
        self.ema = m if self.ema is None else self.ema + (m - self.ema) * 2 / 21
        self.hist.append(self.ema)
        mom = self.ema - self.hist[0] if len(self.hist) > 200 else 0
        k = [0, 0.5, 0.75, 1.0][V]
        out[s] = join(s, D[s], pos(s), 10) if V == 0 else around(s, D[s], pos(s), 50, self.ema + k * mom, 2, 1)
        # TELLURIUM, JELLY, PEANUT_BUTTER: just join best bid/ask with a cap (P3 squid-ink lesson: keep size small)
        cap = [5, 10, 20, 40][V]
        for s in ("TELLURIUM", "JELLY", "PEANUT_BUTTER"):
            out[s] = join(s, D[s], pos(s), min(cap, LIM[s]))
        # PEARLS: fair = 50,000 - the other four (Prosperity 4 PEBBLES)
        tot = sum(mid[p] for p in PEARLS)
        for s in PEARLS:
            fair = 50000 - (tot - mid[s])
            out[s] = [join(s, D[s], pos(s), 20), around(s, D[s], pos(s), 20, fair, 1, 1),
                      around(s, D[s], pos(s), 20, fair, 2, 1), around(s, D[s], pos(s), 20, fair, 1, 2)][V]
        return {k: v for k, v in out.items() if v}, 0, ""

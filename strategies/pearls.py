"""SEPEHR's products: WHITE_PEARLS, BLACK_PEARLS, GOLDEN_PEARLS, PINK_PEARLS, BLUE_PEARLS.

Owner: Sepehr. Only Sepehr edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.
"""

"""Order-size optimized pearl strategy; standard-library only."""

import math
from datamodel import Order, TradingState


class PearlStrategy:
    LIMITS = {
        p: 20 for p in (
            'WHITE_PEARLS',
            'BLACK_PEARLS',
            'GOLDEN_PEARLS',
            'PINK_PEARLS',
            'BLUE_PEARLS'
        )
    }

    PARAMS = {
        'WHITE_PEARLS': dict(
            cap=5, size=5, edge=1, skew=.25,
            alpha=.15, mode='make'
        ),
        'BLACK_PEARLS': dict(
            cap=0, size=0, edge=2, skew=.5,
            alpha=.20, mode='guard'
        ),
        'GOLDEN_PEARLS': dict(
            cap=3, size=3, edge=1, skew=.35,
            alpha=.30, mode='stable'
        ),
        'PINK_PEARLS': dict(
            cap=5, size=1, edge=1, skew=.20,
            alpha=.15, mode='make'
        ),
        'BLUE_PEARLS': dict(
            cap=0, size=0, edge=2, skew=.5,
            alpha=.25, mode='guard'
        ),
    }

    THRESHOLD = 4.0
    PRICE_SHIFT = 0.0
    INVENTORY_SKEW = 1.0
    QUOTE_EDGE = 0.0
    INVENTORY_CAP = 2.0
    EXIT_BIAS = 0.0

    def trade(self, state: TradingState, mem: dict):
        result = {}

        for product, p in self.PARAMS.items():
            depth = state.order_depths.get(product)

            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue

            bid = max(depth.buy_orders)
            ask = min(depth.sell_orders)

            if bid >= ask:
                continue

            mid = (bid + ask) / 2

            rec = mem.setdefault(product, {})

            prev = rec.get('mid', mid)

            ema = rec.get('ema', mid) + p['alpha'] * (
                mid - rec.get('ema', mid)
            )

            movement = abs(mid - prev)

            vol = rec.get('vol', movement) + .05 * (
                movement - rec.get('vol', movement)
            )

            rec.update(mid=mid, ema=ema, vol=vol)

            history = rec.setdefault('history', [])
            history.append(mid)

            if len(history) > 21:
                del history[:-21]

            if p['cap'] == 0:
                continue

            pos = state.position.get(product, 0)

            cool = max(0, rec.get('cool', 0) - 1)

            if (
                p['mode'] == 'stable'
                and abs(mid - ema) > max(5, 4 * vol)
            ):
                cool = 15

            elif (
                p['mode'] == 'guard'
                and abs(mid - ema) > max(10, 5 * vol)
            ):
                cool = 10

            rec['cool'] = cool

            mom = (
                mid - history[-6]
                if len(history) > 5
                else 0.
            )

            cap = min(
                20,
                max(1, round(p['cap'] * self.INVENTORY_CAP))
            )

            reservation = (
                mid
                - p['skew'] * self.INVENTORY_SKEW * pos
                + self.PRICE_SHIFT * max(-8, min(8, mom))
            )

            edge = p['edge'] + self.QUOTE_EDGE

            buy_price = min(
                bid,
                math.floor(reservation - edge),
                ask - 1
            )

            sell_price = max(
                ask,
                math.ceil(reservation + edge),
                bid + 1
            )

            if pos < 0:
                buy_price = min(
                    ask - 1,
                    buy_price + int(self.EXIT_BIAS)
                )

            if pos > 0:
                sell_price = max(
                    bid + 1,
                    sell_price - int(self.EXIT_BIAS)
                )

            buy_qty = max(
                0,
                min(p['size'], cap - pos, 20 - pos)
            )

            sell_qty = max(
                0,
                min(p['size'], cap + pos, 20 + pos)
            )

            allow_buy = mom >= -self.THRESHOLD
            allow_sell = mom <= self.THRESHOLD

            orders = []

            if buy_qty and allow_buy and (cool == 0 or pos < 0):
                orders.append(
                    Order(product, int(buy_price), int(buy_qty))
                )

            if sell_qty and allow_sell and (cool == 0 or pos > 0):
                orders.append(
                    Order(product, int(sell_price), -int(sell_qty))
                )

            if orders:
                result[product] = orders

        return result


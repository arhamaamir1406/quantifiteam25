"""The Trader class UTEFA calls every tick. It doesn't make trading decisions itself:
it asks each strategy class for its orders, makes sure no order breaks a position
limit, and hands everything back.

SHARED FILE: don't change it without telling the whole team (it affects everyone).
"""
import json
from typing import Dict, List, Optional

from datamodel import Order, TradingState
from strategies.core import CoreStrategy
from strategies.fruit_lychee import FruitLycheeStrategy
from strategies.pearls import PearlStrategy


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

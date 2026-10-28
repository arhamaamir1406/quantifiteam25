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

        # Starter: AMETHYST sat at exactly 10,000 every tick of all three training days,
        # so buy just below and sell just above it.
        depth = state.order_depths.get("AMETHYST")
        if depth is not None:
            position = state.position.get("AMETHYST", 0)
            result["AMETHYST"] = market_make(
                "AMETHYST", depth, position, self.LIMITS["AMETHYST"], fair=10_000
            )

        # TODO (Ali): the other 5 products. See README "Starting point" before reusing
        # market_make on them: on its own it loses money on most products.
        return result

"""SEPEHR's products: WHITE_PEARLS, BLACK_PEARLS, GOLDEN_PEARLS, PINK_PEARLS, BLUE_PEARLS.

Owner: Sepehr. Only Sepehr edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.
"""
from typing import Dict, List

from datamodel import Order, TradingState


class PearlStrategy:
    LIMITS = {
        "WHITE_PEARLS": 20,
        "BLACK_PEARLS": 20,
        "GOLDEN_PEARLS": 20,
        "PINK_PEARLS": 20,
        "BLUE_PEARLS": 20,
    }

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        """Called every tick. Return {product: [Order, ...]}.
        `mem` is this file's private memory: whatever you put in it comes back next tick."""
        result: Dict[str, List[Order]] = {}
        # TODO (Sepehr): the 5 pearls.
        return result

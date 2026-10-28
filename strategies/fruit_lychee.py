"""ARHAM's products: DRAGONFRUIT, GRANADILLA, MANGOSTEEN, FRUIT_BASKET, LYCHEE, and the
10 LYCHEE vouchers (call options; symbols in the data are VOUCHER_6800 ... VOUCHER_8100).

Owner: Arham. Only Arham edits this file.
Rule for build.py: keep ALL your code inside the class (no top-level functions or
variables), so nothing clashes with the other strategy files once they're pasted together.
"""
from typing import Dict, List

from datamodel import Order, TradingState


class FruitLycheeStrategy:
    STRIKES = [6800, 7000, 7200, 7300, 7400, 7500, 7600, 7750, 7900, 8100]
    LIMITS = {
        "DRAGONFRUIT": 40,
        "GRANADILLA": 40,
        "MANGOSTEEN": 40,
        "FRUIT_BASKET": 40,
        "LYCHEE": 200,
        **{f"VOUCHER_{k}": 50 for k in STRIKES},
    }

    def trade(self, state: TradingState, mem: dict) -> Dict[str, List[Order]]:
        """Called every tick. Return {product: [Order, ...]}.
        `mem` is this file's private memory: whatever you put in it comes back next tick."""
        result: Dict[str, List[Order]] = {}
        # TODO (Arham): basket vs fruits, and voucher pricing off LYCHEE.
        return result

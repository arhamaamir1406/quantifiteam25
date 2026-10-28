"""Shared helpers every strategy can use.

SHARED FILE: don't change it without telling the whole team (it affects everyone).
build.py pastes this file into the submission first, so these names are
available to every strategy class below it.
"""
import math
from typing import Dict, List, Optional

from datamodel import Order, OrderDepth


def best_bid(depth: OrderDepth) -> Optional[int]:
    return max(depth.buy_orders) if depth.buy_orders else None


def best_ask(depth: OrderDepth) -> Optional[int]:
    return min(depth.sell_orders) if depth.sell_orders else None


def mid_price(depth: OrderDepth) -> Optional[float]:
    bid, ask = best_bid(depth), best_ask(depth)
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2


def market_make(
    product: str,
    depth: OrderDepth,
    position: int,
    limit: int,
    fair: Optional[float] = None,
    edge: float = 1,
    size: Optional[int] = None,
    skew: float = 0,
) -> List[Order]:
    """Baseline strategy: take anything mispriced vs `fair`, then quote 1 tick
    inside the best bid/ask (but never closer than `edge` to fair).

    fair defaults to the current mid price. `size` caps each resting quote.
    `skew` lowers our fair value when we're long (raises it when short) by
    skew x spread at a full position, so we stop piling into a trend.
    Everyone is expected to replace this with something smarter for their own products.
    """
    orders: List[Order] = []
    bid, ask = best_bid(depth), best_ask(depth)
    if bid is None or ask is None:
        return orders
    if fair is None:
        fair = (bid + ask) / 2
    fair -= skew * (ask - bid) * position / limit
    can_buy = limit - position
    can_sell = limit + position

    # 1. Take: buy asks that are clearly below fair, sell into bids clearly above it
    for price in sorted(depth.sell_orders):
        if price > fair - edge or can_buy <= 0:
            break
        qty = min(-depth.sell_orders[price], can_buy)
        orders.append(Order(product, price, qty))
        can_buy -= qty
    for price in sorted(depth.buy_orders, reverse=True):
        if price < fair + edge or can_sell <= 0:
            break
        qty = min(depth.buy_orders[price], can_sell)
        orders.append(Order(product, price, -qty))
        can_sell -= qty

    # 2. Make: rest the remaining capacity just inside the spread
    quote_bid = min(bid + 1, math.floor(fair - edge))
    quote_ask = max(ask - 1, math.ceil(fair + edge))
    if size is not None:
        can_buy, can_sell = min(can_buy, size), min(can_sell, size)
    if can_buy > 0:
        orders.append(Order(product, quote_bid, can_buy))
    if can_sell > 0:
        orders.append(Order(product, quote_ask, -can_sell))
    return orders

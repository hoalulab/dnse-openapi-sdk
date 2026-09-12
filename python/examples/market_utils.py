#!/usr/bin/env python3
"""Small shared market helpers for the examples."""


def to_order_price(market_type, price):
    """Convert a secdef/stream price into the unit the order API expects.

    STOCK prices are quoted in thousands of VND, but the order API wants VND,
    so multiply by 1000 (e.g. 23.1 -> 23100). DERIVATIVE (index futures) prices
    are index points and are sent unchanged.
    """
    if market_type == "STOCK":
        return int(round(price * 1000))
    return price

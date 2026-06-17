"""
TieredPricing — different price per unit depending on the tier the quantity falls into.

This is the "cumulative" / "stacked" tier model, NOT the "volume" model:
    Tiers: [(0, 1000, ₹2.00), (1000, 5000, ₹1.50), (5000, None, ₹1.00)]
    Quantity = 6000:
        First 1000 units  @ ₹2.00 = ₹2000
        Next  4000 units  @ ₹1.50 = ₹6000
        Last  1000 units  @ ₹1.00 = ₹1000
        ------------------------------------
        Total                     = ₹9000

A tier with `to_units = None` is the open-ended top tier.

Tier boundaries are HALF-OPEN on the right: a tier (from, to, price)
covers units strictly less than `to` (i.e. [from, to)).
"""

from dataclasses import dataclass
from typing import Optional

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


@dataclass(frozen=True)
class Tier:
    from_units: int
    to_units: Optional[int]   # None means "unlimited" / open-ended
    unit_price: Money


class TieredPricing(PricingStrategy):
    """Charges across multiple price tiers based on cumulative quantity."""
from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy, Tier


class TieredPricing(PricingStrategy):
    """Charges based on tiers of usage."""

    def __init__(self, tiers: list[Tier]) -> None:
        if not tiers:
            raise ValueError("tiers cannot be empty")

        # Validate contiguous ranges and currency consistency
        for i in range(len(tiers) - 1):
            if tiers[i+1].from_units != tiers[i].to_units:
                raise ValueError("tiers must be contiguous")
        for i, tier in enumerate(tiers):
            if tier.to_units is None and i != len(tiers) - 1:
                raise ValueError("only last tier can be open-ended")

        currencies = {tier.unit_price.currency for tier in tiers}
        if len(currencies) != 1:
            raise ValueError("all tiers must use the same currency")

        self.tiers = tiers

    def calculate(self, quantity: int) -> Money:
        if quantity < 0:
            raise ValueError("quantity cannot be negative")

        currency = self.tiers[0].unit_price.currency
        total = Money.zero(currency)

        for tier in self.tiers:
            if quantity <= tier.from_units:
                continue
            if tier.to_units is None:
                units_in_tier = quantity - tier.from_units
            else:
                units_in_tier = min(quantity, tier.to_units) - tier.from_units
            total += tier.unit_price * units_in_tier

        return total


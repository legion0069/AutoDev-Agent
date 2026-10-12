"""
test_resource_marketplace.py - Unit Tests for ResourceMarketplace (AutoDev Version 3.5)
"""

import pytest

from core.resource_marketplace import (
    MarketOrder,
    OrderType,
    ResourceMarketplace,
    ResourceType,
    TradeSettlement,
)


def test_marketplace_initialization():
    mkt = ResourceMarketplace()
    summary = mkt.get_marketplace_summary()
    assert summary["total_orders_placed"] == 0
    assert summary["total_settled_trades"] == 0
    assert summary["total_transacted_volume_usd"] == 0.0


def test_order_placement_without_immediate_match():
    mkt = ResourceMarketplace()
    ask = mkt.place_ask(
        company_id="COMP-A",
        resource_type=ResourceType.ENGINEERING_HOURS,
        units=50.0,
        price_per_unit_usd=150.0,
    )
    assert ask.order_id.startswith("ORD-")
    assert ask.status == "OPEN"
    assert ask.remaining_units == 50.0

    depth = mkt.get_market_depth(ResourceType.ENGINEERING_HOURS)
    assert depth["total_supply_available"] == 50.0
    assert depth["total_demand_wanted"] == 0.0
    assert depth["lowest_ask_price"] == 150.0


def test_full_order_matching_and_settlement():
    mkt = ResourceMarketplace()

    # Company A offers 40 hours at $100/hr
    ask = mkt.place_ask("COMP-A", ResourceType.ENGINEERING_HOURS, units=40.0, price_per_unit_usd=100.0)

    # Company B bids for 40 hours at $120/hr
    bid = mkt.place_bid("COMP-B", ResourceType.ENGINEERING_HOURS, units=40.0, max_price_per_unit_usd=120.0)

    # Should match immediately!
    # Fair split clearing price = (100 + 120) / 2 = $110/hr
    assert ask.status == "FILLED"
    assert bid.status == "FILLED"
    assert ask.remaining_units == 0.0
    assert bid.remaining_units == 0.0

    summary = mkt.get_marketplace_summary()
    assert summary["total_settled_trades"] == 1
    # 40 * 110 = $4,400
    assert summary["total_transacted_volume_usd"] == 4400.0

    trade = summary["recent_trades"][0]
    assert trade["seller_company_id"] == "COMP-A"
    assert trade["buyer_company_id"] == "COMP-B"
    assert trade["settled_price_per_unit_usd"] == 110.0


def test_partial_order_matching():
    mkt = ResourceMarketplace()

    # Seller offers 100 units at $50
    ask = mkt.place_ask("COMP-A", ResourceType.GPU_ALLOCATION, units=100.0, price_per_unit_usd=50.0)

    # Buyer only wants 30 units at $60
    bid = mkt.place_bid("COMP-B", ResourceType.GPU_ALLOCATION, units=30.0, max_price_per_unit_usd=60.0)

    assert bid.status == "FILLED"
    assert ask.status == "PARTIALLY_FILLED"
    assert ask.remaining_units == 70.0

    depth = mkt.get_market_depth(ResourceType.GPU_ALLOCATION)
    assert depth["total_supply_available"] == 70.0
    assert depth["total_demand_wanted"] == 0.0


def test_no_match_when_spread_is_negative():
    mkt = ResourceMarketplace()

    # Seller asks $200
    ask = mkt.place_ask("COMP-A", ResourceType.SECURITY_AUDIT, units=10.0, price_per_unit_usd=200.0)

    # Buyer only willing to pay $150
    bid = mkt.place_bid("COMP-B", ResourceType.SECURITY_AUDIT, units=10.0, max_price_per_unit_usd=150.0)

    # No trade should execute
    assert ask.status == "OPEN"
    assert bid.status == "OPEN"
    summary = mkt.get_marketplace_summary()
    assert summary["total_settled_trades"] == 0


def test_cancel_order():
    mkt = ResourceMarketplace()
    order = mkt.place_ask("COMP-A", ResourceType.TESTING_CAPACITY, units=25.0, price_per_unit_usd=80.0)
    assert order.status == "OPEN"

    assert mkt.cancel_order(order.order_id) is True
    assert order.status == "CANCELLED"

    depth = mkt.get_market_depth(ResourceType.TESTING_CAPACITY)
    assert depth["total_supply_available"] == 0.0

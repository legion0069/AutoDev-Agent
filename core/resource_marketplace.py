"""
resource_marketplace.py - Enterprise Cross-Company Resource Marketplace (AutoDev Version 3.5)

Facilitates autonomous resource trading between federated companies:
- Engineering hours, Compute infrastructure, GPU clusters, Budget quotas,
  Testing capacity, Security audits, Documentation support, Architecture consulting.
- Continuous double-auction / order-book matching engine.
- Dynamic market clearing price calculation based on supply and demand ratios.
- Transaction settlement ledger with immutable records.
- 100% Python Standard Library.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AutoDev.Federation.Marketplace")


class ResourceType(str, enum.Enum):
    """Tradable corporate resources across the enterprise federation."""
    ENGINEERING_HOURS = "ENGINEERING_HOURS"
    INFRASTRUCTURE_CPU = "INFRASTRUCTURE_CPU"
    GPU_ALLOCATION = "GPU_ALLOCATION"
    BUDGET_USD = "BUDGET_USD"
    TESTING_CAPACITY = "TESTING_CAPACITY"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    DOCUMENTATION_SUPPORT = "DOCUMENTATION_SUPPORT"
    ARCHITECTURE_CONSULTING = "ARCHITECTURE_CONSULTING"


class OrderType(str, enum.Enum):
    """Listing / Order direction."""
    ASK = "ASK"  # Seller offering resource
    BID = "BID"  # Buyer requesting resource


@dataclass
class MarketOrder:
    """An order submitted to the marketplace."""
    order_id: str
    company_id: str
    order_type: OrderType
    resource_type: ResourceType
    total_units: float
    remaining_units: float
    price_per_unit_usd: float
    status: str = "OPEN"  # OPEN, PARTIALLY_FILLED, FILLED, CANCELLED
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeSettlement:
    """An executed transaction between buyer and seller."""
    trade_id: str
    seller_company_id: str
    buyer_company_id: str
    resource_type: ResourceType
    units_transacted: float
    settled_price_per_unit_usd: float
    total_transaction_value_usd: float
    timestamp: float = field(default_factory=time.time)


class ResourceMarketplace:
    """
    Autonomous corporate marketplace executing continuous matching and resource optimization.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._orders: Dict[str, MarketOrder] = {}
        # Order books by ResourceType
        self._asks: Dict[ResourceType, List[MarketOrder]] = {rt: [] for rt in ResourceType}
        self._bids: Dict[ResourceType, List[MarketOrder]] = {rt: [] for rt in ResourceType}
        self._settlements: List[TradeSettlement] = []

    def place_ask(
        self,
        company_id: str,
        resource_type: ResourceType | str,
        units: float,
        price_per_unit_usd: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MarketOrder:
        """Publishes an offering (ASK) to sell resources."""
        return self._submit_order(
            company_id=company_id,
            order_type=OrderType.ASK,
            resource_type=resource_type,
            units=units,
            price_per_unit=price_per_unit_usd,
            metadata=metadata,
        )

    def place_bid(
        self,
        company_id: str,
        resource_type: ResourceType | str,
        units: float,
        max_price_per_unit_usd: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MarketOrder:
        """Publishes a bid (BID) to acquire resources."""
        return self._submit_order(
            company_id=company_id,
            order_type=OrderType.BID,
            resource_type=resource_type,
            units=units,
            price_per_unit=max_price_per_unit_usd,
            metadata=metadata,
        )

    def _submit_order(
        self,
        company_id: str,
        order_type: OrderType,
        resource_type: ResourceType | str,
        units: float,
        price_per_unit: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MarketOrder:
        """Internal order creation and triggering of matching engine."""
        with self._lock:
            oid = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            rt = ResourceType(resource_type) if isinstance(resource_type, str) else resource_type
            order = MarketOrder(
                order_id=oid,
                company_id=company_id,
                order_type=order_type,
                resource_type=rt,
                total_units=float(units),
                remaining_units=float(units),
                price_per_unit_usd=float(price_per_unit),
                metadata=metadata or {},
            )
            self._orders[oid] = order

            if order_type == OrderType.ASK:
                self._asks[rt].append(order)
                # Sort asks: lowest price first
                self._asks[rt].sort(key=lambda o: (o.price_per_unit_usd, o.created_at))
            else:
                self._bids[rt].append(order)
                # Sort bids: highest price first
                self._bids[rt].sort(key=lambda o: (-o.price_per_unit_usd, o.created_at))

            # Trigger automated matching engine
            self._match_orders(rt)
            return order

    def _match_orders(self, resource_type: ResourceType) -> None:
        """
        Continuous double auction matching:
        Matches highest BID with lowest ASK when Bid Price >= Ask Price.
        Clearing price is set halfway between bid and ask (fair split).
        """
        asks = self._asks[resource_type]
        bids = self._bids[resource_type]

        while asks and bids:
            best_ask = asks[0]
            best_bid = bids[0]

            # Cannot trade with self
            if best_ask.company_id == best_bid.company_id:
                # If same company, skip if alternative exists or break
                if len(bids) > 1 and bids[1].price_per_unit_usd >= best_ask.price_per_unit_usd:
                    best_bid = bids[1]
                else:
                    break

            if best_bid.price_per_unit_usd >= best_ask.price_per_unit_usd:
                # Match found!
                units_to_trade = min(best_ask.remaining_units, best_bid.remaining_units)
                clearing_price = round((best_ask.price_per_unit_usd + best_bid.price_per_unit_usd) / 2.0, 2)
                total_val = round(units_to_trade * clearing_price, 2)

                tid = f"TRD-{uuid.uuid4().hex[:8].upper()}"
                settlement = TradeSettlement(
                    trade_id=tid,
                    seller_company_id=best_ask.company_id,
                    buyer_company_id=best_bid.company_id,
                    resource_type=resource_type,
                    units_transacted=units_to_trade,
                    settled_price_per_unit_usd=clearing_price,
                    total_transaction_value_usd=total_val,
                )
                self._settlements.append(settlement)

                # Update orders
                best_ask.remaining_units -= units_to_trade
                best_bid.remaining_units -= units_to_trade

                if best_ask.remaining_units <= 0.0001:
                    best_ask.status = "FILLED"
                    asks.pop(0)
                else:
                    best_ask.status = "PARTIALLY_FILLED"

                if best_bid.remaining_units <= 0.0001:
                    best_bid.status = "FILLED"
                    bids.remove(best_bid)
                else:
                    best_bid.status = "PARTIALLY_FILLED"

                logger.info(
                    "Settled Trade %s: %s sold %.1f of %s to %s at $%.2f/unit ($%.2f)",
                    tid, settlement.seller_company_id, units_to_trade, resource_type.value,
                    settlement.buyer_company_id, clearing_price, total_val,
                )
            else:
                # Price spread does not overlap
                break

    def cancel_order(self, order_id: str) -> bool:
        """Cancels an open order."""
        with self._lock:
            order = self._orders.get(order_id)
            if not order or order.status in ("FILLED", "CANCELLED"):
                return False

            order.status = "CANCELLED"
            rt = order.resource_type
            if order in self._asks[rt]:
                self._asks[rt].remove(order)
            if order in self._bids[rt]:
                self._bids[rt].remove(order)
            return True

    def get_market_depth(self, resource_type: ResourceType | str) -> Dict[str, Any]:
        """Calculates current supply, demand, and implied equilibrium price."""
        with self._lock:
            rt = ResourceType(resource_type) if isinstance(resource_type, str) else resource_type
            active_asks = [o for o in self._asks[rt] if o.status in ("OPEN", "PARTIALLY_FILLED")]
            active_bids = [o for o in self._bids[rt] if o.status in ("OPEN", "PARTIALLY_FILLED")]

            total_supply = sum(o.remaining_units for o in active_asks)
            total_demand = sum(o.remaining_units for o in active_bids)

            avg_ask = (sum(o.price_per_unit_usd * o.remaining_units for o in active_asks) / max(1, total_supply)) if total_supply > 0 else 0.0
            avg_bid = (sum(o.price_per_unit_usd * o.remaining_units for o in active_bids) / max(1, total_demand)) if total_demand > 0 else 0.0

            return {
                "resource_type": rt.value,
                "total_supply_available": round(total_supply, 2),
                "total_demand_wanted": round(total_demand, 2),
                "lowest_ask_price": active_asks[0].price_per_unit_usd if active_asks else None,
                "highest_bid_price": active_bids[0].price_per_unit_usd if active_bids else None,
                "weighted_average_ask": round(avg_ask, 2),
                "weighted_average_bid": round(avg_bid, 2),
            }

    def get_marketplace_summary(self) -> Dict[str, Any]:
        """Returns macro trading volume and settlement metrics."""
        with self._lock:
            total_volume = sum(t.total_transaction_value_usd for t in self._settlements)
            return {
                "total_orders_placed": len(self._orders),
                "total_settled_trades": len(self._settlements),
                "total_transacted_volume_usd": round(total_volume, 2),
                "open_asks_count": sum(len(asks) for asks in self._asks.values()),
                "open_bids_count": sum(len(bids) for bids in self._bids.values()),
                "recent_trades": [
                    asdict(t) for t in self._settlements[-5:]
                ],
            }

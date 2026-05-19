"""Pure orderbook matcher for CivitasLab.

Merged Package 2 introduces this module as a side-effect-free boundary around the
orderbook matching semantics.  It intentionally works only on plain dataclasses
or dictionaries and does not import or mutate ``model.Environment`` objects.

The current live market path is **not** replaced by this module.  CLI tools use it
for shadow comparison and future Rust/PyO3 equivalence tests.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import ceil
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple
import copy


@dataclass
class OrderbookSellOrder:
    order_id: str
    seller_type: str
    seller_id: str
    seller_population: str
    good: str
    quantity: int
    unit_price: int
    order_index: int = 0
    historical_quantity: int = 0
    allow_cross_tribe: bool = True
    source_kind: str = "live_snapshot"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderbookDemandItem:
    demand_id: str
    buyer_type: str
    buyer_id: str
    buyer_population: str
    good: str
    need_kind: str
    desired_quantity: int
    priority: int = 0
    sequence: int = 0
    budget_cap: int = 0
    willingness: int = 0
    allow_cross_tribe: bool = False
    cap_rule: str = "fixed"  # fixed | individual_hard | reproduction_hard | government
    dynamic_need: bool = False
    source_kind: str = "fixture"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderbookBuyerState:
    buyer_type: str
    buyer_id: str
    population: str
    money: int
    inventory: Dict[str, int] = field(default_factory=dict)
    reserved_budget: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderbookTradeRecord:
    trade_id: str
    good: str
    seller_type: str
    seller_id: str
    seller_population: str
    buyer_type: str
    buyer_id: str
    buyer_population: str
    quantity: int
    unit_price: int
    total_value: int
    need_kind: str
    demand_id: str
    order_id: str
    source_kind: str = "pure_matcher"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OrderbookMatchResult:
    trades: List[OrderbookTradeRecord]
    remaining_sell_orders: List[OrderbookSellOrder]
    remaining_demands: List[OrderbookDemandItem]
    buyer_money_delta: Dict[str, int]
    seller_money_delta: Dict[str, int]
    buyer_inventory_delta: Dict[str, Dict[str, int]]
    seller_inventory_delta: Dict[str, Dict[str, int]]
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trades": [t.to_dict() for t in self.trades],
            "remaining_sell_orders": [o.to_dict() for o in self.remaining_sell_orders],
            "remaining_demands": [d.to_dict() for d in self.remaining_demands],
            "buyer_money_delta": dict(self.buyer_money_delta),
            "seller_money_delta": dict(self.seller_money_delta),
            "buyer_inventory_delta": copy.deepcopy(self.buyer_inventory_delta),
            "seller_inventory_delta": copy.deepcopy(self.seller_inventory_delta),
            "diagnostics": copy.deepcopy(self.diagnostics),
        }


def goods_cost(quantity: int, unit_price: int) -> int:
    quantity = max(0, int(quantity))
    if quantity <= 0:
        return 0
    return max(1, int(ceil(quantity * max(1, int(unit_price)) / 100)))


def _as_order(value: Mapping[str, Any] | OrderbookSellOrder, idx: int = 0) -> OrderbookSellOrder:
    if isinstance(value, OrderbookSellOrder):
        return copy.deepcopy(value)
    amount = value.get("quantity", value.get("amount", value.get("available_quantity", 0)))
    return OrderbookSellOrder(
        order_id=str(value.get("order_id", f"order_{idx}")),
        seller_type=str(value.get("seller_type", "unknown")),
        seller_id=str(value.get("seller_id", "")),
        seller_population=str(value.get("seller_population", value.get("seller_pop", ""))),
        good=str(value.get("good", "")),
        quantity=max(0, int(amount or 0)),
        unit_price=max(1, int(value.get("unit_price", value.get("price_index", 1)) or 1)),
        order_index=int(value.get("order_index", idx) or 0),
        historical_quantity=max(0, int(value.get("historical_quantity", value.get("historical_amount", 0)) or 0)),
        allow_cross_tribe=bool(value.get("allow_cross_tribe", True)),
        source_kind=str(value.get("source_kind", "live_snapshot")),
    )


def _as_demand(value: Mapping[str, Any] | OrderbookDemandItem, idx: int = 0) -> OrderbookDemandItem:
    if isinstance(value, OrderbookDemandItem):
        return copy.deepcopy(value)
    return OrderbookDemandItem(
        demand_id=str(value.get("demand_id", f"demand_{idx}")),
        buyer_type=str(value.get("buyer_type", "individual")),
        buyer_id=str(value.get("buyer_id", "")),
        buyer_population=str(value.get("buyer_population", value.get("population", ""))),
        good=str(value.get("good", "")),
        need_kind=str(value.get("need_kind", "unknown")),
        desired_quantity=max(0, int(value.get("desired_quantity", value.get("need_amount", 0)) or 0)),
        priority=int(value.get("priority", 0) or 0),
        sequence=int(value.get("sequence", idx) or 0),
        budget_cap=max(0, int(value.get("budget_cap", value.get("estimated_spending_cap", 0)) or 0)),
        willingness=max(0, int(value.get("willingness", value.get("effective_willingness", 0)) or 0)),
        allow_cross_tribe=bool(value.get("allow_cross_tribe", False)),
        cap_rule=str(value.get("cap_rule", "fixed")),
        dynamic_need=bool(value.get("dynamic_need", False)),
        source_kind=str(value.get("source_kind", "fixture")),
    )


def _as_buyer(value: Mapping[str, Any] | OrderbookBuyerState) -> OrderbookBuyerState:
    if isinstance(value, OrderbookBuyerState):
        return copy.deepcopy(value)
    return OrderbookBuyerState(
        buyer_type=str(value.get("buyer_type", "individual")),
        buyer_id=str(value.get("buyer_id", "")),
        population=str(value.get("population", value.get("buyer_population", ""))),
        money=max(0, int(value.get("money", value.get("balance", 0)) or 0)),
        inventory={str(k): int(v or 0) for k, v in dict(value.get("inventory", {}) or {}).items()},
        reserved_budget=max(0, int(value.get("reserved_budget", 0) or 0)),
        metadata=copy.deepcopy(dict(value.get("metadata", {}) or {})),
    )


def _buyer_meta_int(buyer: OrderbookBuyerState, key: str, default: int = 0) -> int:
    try:
        return int(buyer.metadata.get(key, default) or default)
    except Exception:
        return int(default)


def _is_rich(buyer: OrderbookBuyerState) -> bool:
    return int(buyer.money) >= _buyer_meta_int(buyer, "wealth_tax_threshold", 1500)


def _is_poor(buyer: OrderbookBuyerState) -> bool:
    return int(buyer.money) < _buyer_meta_int(buyer, "survival_cost", 100)


def _market_spending_ratio(buyer: OrderbookBuyerState, good: str) -> float:
    survival_cost = _buyer_meta_int(buyer, "survival_cost", 100)
    if good == "food":
        return 0.8
    if good == "medical_goods":
        return 0.7 if bool(buyer.metadata.get("is_sick", False)) else 0.2
    if good == "reproduction_goods":
        return 0.4 if int(buyer.money) > 0 else 0.0
    if good == "education_goods":
        return 0.3 if int(buyer.money) >= survival_cost * 2 else 0.0
    return 0.0


def _market_spending_limit(buyer: OrderbookBuyerState, good: str) -> int:
    balance = max(0, int(buyer.money))
    survival_cost = _buyer_meta_int(buyer, "survival_cost", 100)
    child_cost = _buyer_meta_int(buyer, "child_cost", 100)
    if good == "reproduction_goods":
        if _is_reproduction_hard_buyer(buyer):
            food_shortage = max(0, survival_cost - int(buyer.inventory.get("food", 0)))
            food_price = _buyer_meta_int(buyer, "food_price_index", 100)
            food_emergency_reserve = int(ceil(food_shortage * food_price / 100)) if food_shortage > 0 else 0
            return max(0, balance - food_emergency_reserve)
        return int(balance * _market_spending_ratio(buyer, good))
    if good == "education_goods":
        return max(0, balance - child_cost - survival_cost)
    return int(balance * _market_spending_ratio(buyer, good))


def _individual_effective_willingness(buyer: OrderbookBuyerState, demand: OrderbookDemandItem) -> Tuple[int, int, int]:
    # Live hard needs are not compressed by willingness.  For reserve/education,
    # the adapter stores the precomputed effective willingness for the buyer/good.
    if demand.need_kind in {"food_hard", "medical_hard", "reproduction_hard", "hard"}:
        return int(demand.willingness or 100), 100, 0
    base = max(0, min(100, int(demand.willingness or buyer.metadata.get("individual_buy_willingness", 80))))
    return base, base, 0


def _is_reproduction_hard_buyer(buyer: OrderbookBuyerState) -> bool:
    survival_cost = _buyer_meta_int(buyer, "survival_cost", 100)
    child_cost = _buyer_meta_int(buyer, "child_cost", 100)
    return (
        not bool(buyer.metadata.get("critical", False))
        and not bool(buyer.metadata.get("is_sick", False))
        and int(buyer.inventory.get("food", 0)) >= survival_cost
        and _buyer_meta_int(buyer, "reproduce", 0) >= 10
        and int(buyer.inventory.get("reproduction_goods", 0)) < child_cost
    )


def _target_stock(buyer: OrderbookBuyerState, good: str) -> int:
    survival_cost = _buyer_meta_int(buyer, "survival_cost", 100)
    child_cost = _buyer_meta_int(buyer, "child_cost", 100)
    rich = _is_rich(buyer)
    poor = _is_poor(buyer)
    reproduce = _buyer_meta_int(buyer, "reproduce", 0)
    sick = bool(buyer.metadata.get("is_sick", False))
    critical = bool(buyer.metadata.get("critical", False))
    if good == "food":
        target = survival_cost if poor else survival_cost * 3
        if rich:
            target = int(round(target * 1.5))
        return max(0, target)
    if good == "medical_goods":
        if sick:
            target = survival_cost
        else:
            target = 0 if poor else int(round(survival_cost * 0.3))
        if rich:
            target = int(round(target * 1.5))
        return max(0, target)
    if good == "reproduction_goods":
        if reproduce < 10 or sick or critical:
            return 0
        if int(buyer.inventory.get("food", 0)) < survival_cost:
            return 0
        target = child_cost
        if rich:
            target = int(round(target * 1.5))
        return max(0, target)
    if good == "education_goods":
        if poor or reproduce < 10 or int(buyer.money) <= child_cost + survival_cost:
            return 0
        target = child_cost
        if rich:
            target = int(round(target * 2))
        return max(0, target)
    return 0


def _hard_reserve_need(buyer: OrderbookBuyerState, good: str) -> Tuple[int, int]:
    survival_cost = _buyer_meta_int(buyer, "survival_cost", 100)
    child_cost = _buyer_meta_int(buyer, "child_cost", 100)
    current = int(buyer.inventory.get(good, 0))
    hard = 0
    if good == "food":
        hard = max(0, survival_cost - current)
    elif good == "medical_goods":
        hard = max(0, survival_cost - current) if bool(buyer.metadata.get("is_sick", False)) else 0
    elif good == "reproduction_goods":
        if _is_reproduction_hard_buyer(buyer):
            hard = max(0, child_cost - current)
    elif good == "education_goods":
        if _buyer_meta_int(buyer, "reproduce", 0) >= 10 and int(buyer.money) >= child_cost + survival_cost:
            hard = max(0, int(round(child_cost * 0.25)) - current)
    target = _target_stock(buyer, good)
    total_need = max(0, target - current)
    reserve = max(0, total_need - hard)
    return int(hard), int(reserve)


def _effective_need(demand: OrderbookDemandItem, buyer: OrderbookBuyerState) -> int:
    initial = max(0, int(demand.desired_quantity))
    if not demand.dynamic_need:
        return initial
    hard, reserve = _hard_reserve_need(buyer, demand.good)
    if demand.need_kind in {"hard", "food_hard", "medical_hard", "reproduction_hard"}:
        return max(0, min(initial, int(hard)))
    if demand.need_kind in {"reserve", "food_reserve", "medical_reserve", "reproduction_reserve"}:
        return max(0, min(initial, int(reserve)))
    # Live orderbook_buyer_need_amount returns market_goods_need for education/tools/total.
    target = _target_stock(buyer, demand.good)
    current = int(buyer.inventory.get(demand.good, 0))
    return max(0, min(initial, max(0, target - current, hard)))


def _effective_cap(demand: OrderbookDemandItem, buyer: OrderbookBuyerState, unit_price: int) -> int:
    money = max(0, int(buyer.money))
    if money <= 0:
        return 0
    rule = demand.cap_rule
    if rule == "government":
        willingness = max(0, min(100, int(demand.willingness or buyer.metadata.get("government_buy_willingness", 60))))
        reserve = int(money * (100 - willingness) / 100)
        available = max(0, money - reserve)
        price_factor = min(1.0, max(0.05, 100 / max(1, int(unit_price))))
        return int(available * price_factor)
    if rule == "individual_hard":
        return money
    if rule == "reproduction_hard":
        return int(money * 0.9)
    if demand.dynamic_need:
        _, willingness, _ = _individual_effective_willingness(buyer, demand)
        base_limit = max(0, int(_market_spending_limit(buyer, demand.good)))
        price_factor = min(1.5, max(0.25, 100 / max(1, int(unit_price))))
        cap = int(money * willingness / 100 * price_factor)
        return max(0, min(base_limit, cap, money))
    if demand.budget_cap > 0:
        initial_money = max(1, int(buyer.metadata.get("initial_money", money) or money or 1))
        scaled_cap = int(demand.budget_cap * money / initial_money)
        return min(money, max(0, scaled_cap))
    return money


def match_orderbook(
    sell_orders: Iterable[Mapping[str, Any] | OrderbookSellOrder],
    demand_items: Iterable[Mapping[str, Any] | OrderbookDemandItem],
    buyer_states: Mapping[str, Mapping[str, Any] | OrderbookBuyerState],
    *,
    global_trade_enabled: bool = False,
    resort_orders: bool = True,
) -> OrderbookMatchResult:
    """Match plain sell orders against plain demand items.

    ``demand_items`` must already encode the buyer ordering/priority desired by a
    caller.  The matcher only consumes demand in ascending ``sequence``.
    """
    orders = [_as_order(o, idx) for idx, o in enumerate(sell_orders)]
    demands = [_as_demand(d, idx) for idx, d in enumerate(demand_items)]
    buyers: Dict[str, OrderbookBuyerState] = {str(k): _as_buyer(v) for k, v in buyer_states.items()}
    if resort_orders:
        orders.sort(key=lambda o: (o.good, o.unit_price, -o.quantity, o.order_index))
    else:
        orders.sort(key=lambda o: (o.good, o.order_index))
    demands.sort(key=lambda d: (d.sequence, d.priority, d.demand_id))

    trades: List[OrderbookTradeRecord] = []
    buyer_money_delta: Dict[str, int] = {}
    seller_money_delta: Dict[str, int] = {}
    buyer_inventory_delta: Dict[str, Dict[str, int]] = {}
    seller_inventory_delta: Dict[str, Dict[str, int]] = {}
    remaining_demands: List[OrderbookDemandItem] = []
    skipped = {"self_buy": 0, "cross_tribe": 0, "no_buyer_state": 0, "no_cap": 0, "no_money": 0}

    orders_by_good: Dict[str, List[OrderbookSellOrder]] = {}
    for order in orders:
        if order.quantity > 0:
            orders_by_good.setdefault(order.good, []).append(order)

    for demand in demands:
        buyer = buyers.get(demand.buyer_id)
        if buyer is None:
            skipped["no_buyer_state"] += 1
            remaining_demands.append(copy.deepcopy(demand))
            continue
        remaining_need = _effective_need(demand, buyer)
        if remaining_need <= 0:
            continue
        order_list = orders_by_good.get(demand.good, [])
        for order in order_list:
            if remaining_need <= 0:
                break
            if buyer.money <= 0:
                skipped["no_money"] += 1
                break
            if order.quantity <= 0:
                continue
            if order.seller_type == "individual" and order.seller_id == demand.buyer_id:
                skipped["self_buy"] += 1
                continue
            if order.seller_population != demand.buyer_population and not (global_trade_enabled or demand.allow_cross_tribe or order.allow_cross_tribe is False and False):
                skipped["cross_tribe"] += 1
                continue
            cap = _effective_cap(demand, buyer, order.unit_price)
            if cap <= 0:
                skipped["no_cap"] += 1
                continue
            affordable_qty = int(cap * 100 // max(1, order.unit_price))
            qty = min(remaining_need, order.quantity, affordable_qty)
            while qty > 0 and goods_cost(qty, order.unit_price) > buyer.money:
                qty -= 1
            if qty <= 0:
                skipped["no_money"] += 1
                continue
            cost = goods_cost(qty, order.unit_price)
            if cost <= 0 or cost > buyer.money:
                continue
            order.quantity -= qty
            buyer.money -= cost
            buyer.inventory[demand.good] = int(buyer.inventory.get(demand.good, 0)) + qty
            remaining_need -= qty
            trade = OrderbookTradeRecord(
                trade_id=f"trade_{len(trades)+1}",
                good=demand.good,
                seller_type=order.seller_type,
                seller_id=order.seller_id,
                seller_population=order.seller_population,
                buyer_type=demand.buyer_type,
                buyer_id=demand.buyer_id,
                buyer_population=demand.buyer_population,
                quantity=int(qty),
                unit_price=int(order.unit_price),
                total_value=int(cost),
                need_kind=demand.need_kind,
                demand_id=demand.demand_id,
                order_id=order.order_id,
            )
            trades.append(trade)
            buyer_money_delta[demand.buyer_id] = buyer_money_delta.get(demand.buyer_id, 0) - cost
            seller_money_delta[order.seller_id] = seller_money_delta.get(order.seller_id, 0) + cost
            buyer_inventory_delta.setdefault(demand.buyer_id, {})[demand.good] = buyer_inventory_delta.setdefault(demand.buyer_id, {}).get(demand.good, 0) + qty
            seller_inventory_delta.setdefault(order.seller_id, {})[demand.good] = seller_inventory_delta.setdefault(order.seller_id, {}).get(demand.good, 0) - qty
        if remaining_need > 0:
            d = copy.deepcopy(demand)
            d.desired_quantity = int(remaining_need)
            remaining_demands.append(d)

    remaining_orders = [copy.deepcopy(order) for order in orders if order.quantity > 0]
    diagnostics = {
        "trade_count": len(trades),
        "trade_quantity_total": sum(t.quantity for t in trades),
        "trade_value_total": sum(t.total_value for t in trades),
        "remaining_order_count": len(remaining_orders),
        "remaining_demand_count": len(remaining_demands),
        "skipped": skipped,
    }
    return OrderbookMatchResult(
        trades=trades,
        remaining_sell_orders=remaining_orders,
        remaining_demands=remaining_demands,
        buyer_money_delta=buyer_money_delta,
        seller_money_delta=seller_money_delta,
        buyer_inventory_delta=buyer_inventory_delta,
        seller_inventory_delta=seller_inventory_delta,
        diagnostics=diagnostics,
    )


def summarize_trades(trades: Iterable[Mapping[str, Any] | OrderbookTradeRecord]) -> Dict[str, Any]:
    out = {
        "trade_count": 0,
        "total_quantity": 0,
        "total_value": 0,
        "by_good": {},
        "by_buyer_type": {},
        "by_seller_type": {},
        "by_need_kind": {},
    }
    for item in trades:
        t = item.to_dict() if isinstance(item, OrderbookTradeRecord) else dict(item)
        good = str(t.get("good", "unknown"))
        buyer_type = str(t.get("buyer_type", "unknown"))
        seller_type = str(t.get("seller_type", "unknown"))
        need_kind = str(t.get("need_kind", "unknown"))
        qty = int(t.get("quantity", t.get("amount", 0)) or 0)
        value = int(t.get("total_value", t.get("cost", 0)) or 0)
        out["trade_count"] += 1
        out["total_quantity"] += qty
        out["total_value"] += value
        for key, label in [("by_good", good), ("by_buyer_type", buyer_type), ("by_seller_type", seller_type), ("by_need_kind", need_kind)]:
            bucket = out[key].setdefault(label, {"quantity": 0, "value": 0, "count": 0})
            bucket["quantity"] += qty
            bucket["value"] += value
            bucket["count"] += 1
    return out

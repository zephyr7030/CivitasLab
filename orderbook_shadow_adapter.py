"""Shadow adapter between live CivitasLab Environment state and orderbook_core.

This adapter is deliberately observational.  It converts a copied/pre-market live
state into plain sell orders, demand items and buyer states, then runs the pure
matcher.  It does not replace or mutate the live market path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import copy
import random

from model import TRADED_GOODS, GOOD_FIELDS, NEED_REPRODUCTION_HARD, HARD_NEED_KINDS
from orderbook_core import match_orderbook


@dataclass
class OrderbookFixture:
    turn: int
    mode: str
    sell_orders: List[Dict[str, Any]]
    demand_items: List[Dict[str, Any]]
    buyer_states: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "mode": self.mode,
            "sell_orders": self.sell_orders,
            "demand_items": self.demand_items,
            "buyer_states": self.buyer_states,
            "metadata": self.metadata,
        }


def _buyer_id(ind: Any) -> str:
    return str(getattr(ind, "code", "") or getattr(ind, "id", ""))


def _call(default: Any, func, *args, **kwargs) -> Any:
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def _flatten_orders(raw_orders: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    index = 0
    for good in TRADED_GOODS:
        for order in raw_orders.get(good, []):
            index += 1
            flat.append({
                "order_id": f"{good}_{index}",
                "seller_type": str(order.get("seller_type", "")),
                "seller_id": str(order.get("seller_id", "")),
                "seller_population": str(order.get("seller_pop", "")),
                "good": str(order.get("good", good)),
                "quantity": int(max(0, order.get("amount", 0) or 0)),
                "unit_price": int(max(1, order.get("price_index", 1) or 1)),
                "order_index": index,
                "historical_quantity": int(max(0, order.get("historical_amount", 0) or 0)),
                "allow_cross_tribe": True,
                "source_kind": "env.build_orderbook_sell_orders(copy)",
            })
    flat.sort(key=lambda o: (o["good"], o["unit_price"], -o["quantity"], o["order_index"]))
    return flat


def _buyer_inventory(ind: Any) -> Dict[str, int]:
    return {good: int(getattr(ind, good, 0) or 0) for good in GOOD_FIELDS}


def _individual_buyer_states(env: Any) -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    survival_cost = int(getattr(env, "cfg", {}).get("base", {}).get("survival_cost", 100)) if hasattr(env, "cfg") else 100
    child_cost = int(_call(survival_cost, env.reproduction_goods_required_per_birth)) if hasattr(env, "reproduction_goods_required_per_birth") else survival_cost
    for p, pop in getattr(env, "populations", {}).items():
        cfg = getattr(env, "state", {}).get("population_config", {}).get(p, {}) if hasattr(env, "state") else {}
        for ind in pop:
            bid = _buyer_id(ind)
            states[bid] = {
                "buyer_type": "individual",
                "buyer_id": bid,
                "population": str(p),
                "money": int(max(0, getattr(ind, "balance", 0) or 0)),
                "inventory": _buyer_inventory(ind),
                "metadata": {
                    "critical": bool(getattr(ind, "critical", False)),
                    "is_sick": bool(getattr(ind, "is_sick", 0)),
                    "reproduce": int(getattr(ind, "reproduce", 0) or 0),
                    "wage_received": int(getattr(ind, "wage_received", 0) or 0),
                    "initial_money": int(max(0, getattr(ind, "balance", 0) or 0)),
                    "survival_cost": int(survival_cost),
                    "child_cost": int(child_cost),
                    "wealth_tax_threshold": int(cfg.get("wealth_tax_threshold", 1500)),
                    "wealth_tax_exempt_threshold": int(cfg.get("wealth_tax_exempt_threshold", 600)),
                    "individual_buy_willingness": int(cfg.get("individual_buy_willingness", 80)),
                    "food_price_index": int(max(1, _call(100, env.goods_price_index, p, "food"))) if hasattr(env, "goods_price_index") else 100,
                },
            }
    return states


def _government_buyer_states(env: Any) -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    for p in getattr(env, "population_names", []):
        cfg = getattr(env, "state", {}).get("population_config", {}).get(p, {}) if hasattr(env, "state") else {}
        bid = f"Government:{p}"
        states[bid] = {
            "buyer_type": "government",
            "buyer_id": bid,
            "population": str(p),
            "money": int(max(0, getattr(env, "government_deposit", {}).get(p, 0) or 0)),
            "inventory": {good: int(max(0, _call(0, env.government_good_stock, p, good))) for good in GOOD_FIELDS} if hasattr(env, "government_good_stock") else {},
            "metadata": {"government_buy_willingness": int(cfg.get("government_buy_willingness", 60)), "initial_money": int(max(0, getattr(env, "government_deposit", {}).get(p, 0) or 0))},
        }
    return states


def _cap_rule_for(need_kind: str) -> str:
    if need_kind == NEED_REPRODUCTION_HARD:
        return "reproduction_hard"
    if need_kind in HARD_NEED_KINDS or need_kind == "hard":
        return "individual_hard"
    return "fixed"


def _individual_demand_sequence(env: Any, random_state: Optional[object], mode: str) -> List[Tuple[str, Any, List[Tuple[int, str, str]]]]:
    buyers: List[Tuple[str, Any, List[Tuple[int, str, str]]]] = []
    for p, pop in getattr(env, "populations", {}).items():
        if hasattr(env, "calculate_initial_market_demand_supply"):
            _call(None, env.calculate_initial_market_demand_supply, p, pop, TRADED_GOODS)
        for ind in pop:
            if getattr(ind, "critical", False):
                continue
            total_need = 0
            for good in TRADED_GOODS:
                total_need += int(max(0, _call(0, env.market_goods_need, ind, good))) if hasattr(env, "market_goods_need") else 0
            if total_need > 0:
                plan = _call([], env.orderbook_buyer_demand_plan, ind) if hasattr(env, "orderbook_buyer_demand_plan") else []
                buyers.append((str(p), ind, list(plan)))
    if mode == "adapter_live_sequence":
        # Reproduce the global random.shuffle that live orderbook_individual_purchase_phase will perform.
        old_state = random.getstate()
        try:
            if random_state is not None:
                random.setstate(random_state)
            random.shuffle(buyers)
        finally:
            random.setstate(old_state)
    else:
        buyers.sort(key=lambda item: (item[0], _buyer_id(item[1])))
    return buyers


def build_orderbook_fixture(env: Any, *, random_state: Optional[object] = None, mode: str = "adapter_live_sequence") -> OrderbookFixture:
    """Build a plain orderbook fixture from a pre-market Environment snapshot.

    The function is safe to call on a deep copy of the live environment.  It may
    call live helper methods on that copy to mirror current semantics.
    """
    raw_orders = env.build_orderbook_sell_orders() if hasattr(env, "build_orderbook_sell_orders") else {good: [] for good in TRADED_GOODS}
    sell_orders = _flatten_orders(raw_orders)
    buyer_states = _individual_buyer_states(env)
    buyer_states.update(_government_buyer_states(env))
    global_trade_enabled = bool(_call(False, env.is_feature_enabled, "enable_global_trade")) if hasattr(env, "is_feature_enabled") else False

    demand_items: List[Dict[str, Any]] = []
    seq = 0
    for p, buyer, plan in _individual_demand_sequence(env, random_state, mode):
        bid = _buyer_id(buyer)
        if int(getattr(buyer, "balance", 0) or 0) <= 0 or getattr(buyer, "critical", False):
            continue
        for priority, good, need_kind in plan:
            need = int(max(0, _call(0, env.orderbook_buyer_need_amount, buyer, good, need_kind))) if hasattr(env, "orderbook_buyer_need_amount") else 0
            if need <= 0:
                continue
            price_index = int(max(1, _call(1, env.goods_price_index, p, good))) if hasattr(env, "goods_price_index") else 1
            cap = int(max(0, _call(0, env.individual_orderbook_spending_cap_by_need, buyer, good, price_index, need_kind, need))) if hasattr(env, "individual_orderbook_spending_cap_by_need") else 0
            willingness_tuple = _call((0, 0, 0), env.individual_effective_buy_willingness, buyer, good, need_kind) if hasattr(env, "individual_effective_buy_willingness") else (0, 0, 0)
            willingness = int(willingness_tuple[1]) if isinstance(willingness_tuple, (tuple, list)) and len(willingness_tuple) > 1 else 0
            seq += 1
            demand_items.append({
                "demand_id": f"D{seq:06d}",
                "buyer_type": "individual",
                "buyer_id": bid,
                "buyer_population": str(p),
                "population": str(p),
                "good": str(good),
                "need_kind": str(need_kind),
                "desired_quantity": int(need),
                "priority": int(priority),
                "sequence": seq,
                "budget_cap": int(cap),
                "willingness": int(willingness),
                "allow_cross_tribe": bool(global_trade_enabled),
                "cap_rule": _cap_rule_for(str(need_kind)),
                "dynamic_need": True,
                "source_kind": mode,
            })

    if bool(_call(False, env.is_feature_enabled, "enable_government_orderbook_buyer")) if hasattr(env, "is_feature_enabled") else True:
        for p in getattr(env, "population_names", []):
            cfg = getattr(env, "state", {}).get("population_config", {}).get(p, {}) if hasattr(env, "state") else {}
            willingness = int(max(0, min(100, int(cfg.get("government_buy_willingness", 60)))))
            for good in TRADED_GOODS:
                # Government live path is a last buyer: it iterates current remaining orders.
                # Use initial listed supply as an upper bound; the pure matcher will see only leftovers after individuals.
                need = sum(int(o.get("quantity", 0) or 0) for o in sell_orders if o.get("good") == good)
                if need <= 0:
                    continue
                seq += 1
                demand_items.append({
                    "demand_id": f"G{seq:06d}",
                    "buyer_type": "government",
                    "buyer_id": f"Government:{p}",
                    "buyer_population": str(p),
                    "population": str(p),
                    "good": str(good),
                    "need_kind": "government_last_buyer",
                    "desired_quantity": int(need),
                    "priority": 1000,
                    "sequence": seq,
                    "budget_cap": 0,
                    "willingness": willingness,
                    "allow_cross_tribe": True,
                    "cap_rule": "government",
                    "dynamic_need": False,
                    "source_kind": mode,
                })

    return OrderbookFixture(
        turn=int(getattr(env, "turn", 0)),
        mode=mode,
        sell_orders=sell_orders,
        demand_items=demand_items,
        buyer_states=buyer_states,
        metadata={
            "global_trade_enabled": global_trade_enabled,
            "sell_order_count": len(sell_orders),
            "demand_item_count": len(demand_items),
            "buyer_state_count": len(buyer_states),
            "note": "Built from copied pre-market Environment state; live path not modified.",
        },
    )


def run_pure_match_from_fixture(fixture: OrderbookFixture | Dict[str, Any]) -> Dict[str, Any]:
    data = fixture.to_dict() if isinstance(fixture, OrderbookFixture) else fixture
    result = match_orderbook(
        data.get("sell_orders", []),
        data.get("demand_items", []),
        data.get("buyer_states", {}),
        global_trade_enabled=bool(data.get("metadata", {}).get("global_trade_enabled", False)),
        resort_orders=True,
    )
    return result.to_dict()


def build_fixture_from_live_copy(env: Any, *, random_state: Optional[object] = None, mode: str = "adapter_live_sequence") -> OrderbookFixture:
    env_copy = copy.deepcopy(env)
    return build_orderbook_fixture(env_copy, random_state=random_state, mode=mode)

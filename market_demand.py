"""Demand-plan helpers for CivitasLab orderbook preparation.

Merged Package 1 creates this module as a non-invasive bridge toward the future
orderbook pure-function boundary. The live market path is intentionally not
replaced here: these helpers read the current Environment state and emit plain
records that can be audited, displayed, and later fed into shadow compare tools.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

try:  # Reuse canonical constants when the full model is available.
    from model import TRADED_GOODS, GOOD_DISPLAY
except Exception:  # pragma: no cover - fallback for static tooling.
    TRADED_GOODS = ["food", "medical_goods", "education_goods", "reproduction_goods"]
    GOOD_DISPLAY = {good: good for good in TRADED_GOODS}


@dataclass
class DemandPlanItem:
    turn: int
    buyer_type: str
    buyer_id: str
    population: str
    good: str
    need_kind: str
    priority: int
    need_amount: int
    available_amount: int = 0
    price_index: int = 0
    estimated_spending_cap: int = 0
    effective_willingness: int = 0
    budget_cap_kind: str = "unknown"
    allow_cross_tribe: bool = False
    source: str = "market_demand"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_call(default: Any, func, *args, **kwargs) -> Any:
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


def _buyer_id(buyer: Any) -> str:
    return str(getattr(buyer, "code", "") or getattr(buyer, "id", ""))


def build_individual_demand_plan(env: Any, population: str, buyer: Any, orders: Optional[Dict[str, list]] = None) -> List[DemandPlanItem]:
    """Build a plain demand plan for one individual buyer from live Environment methods.

    The plan mirrors the live priority function ``Environment.orderbook_buyer_demand_plan``
    when available, but stores quantities, estimated caps, and willingness in an
    inspectable format.
    """
    if getattr(buyer, "critical", False):
        return []
    raw_items = _safe_call([], env.orderbook_buyer_demand_plan, buyer) if hasattr(env, "orderbook_buyer_demand_plan") else []
    out: List[DemandPlanItem] = []
    for raw in raw_items:
        if len(raw) < 3:
            continue
        priority, good, need_kind = int(raw[0]), str(raw[1]), str(raw[2])
        need_amount = int(max(0, _safe_call(0, env.orderbook_buyer_need_amount, buyer, good, need_kind))) if hasattr(env, "orderbook_buyer_need_amount") else 0
        if need_amount <= 0:
            continue
        price_index = int(max(1, _safe_call(1, env.goods_price_index, population, good))) if hasattr(env, "goods_price_index") else 1
        cap = 0
        if hasattr(env, "individual_orderbook_spending_cap_by_need"):
            cap = int(max(0, _safe_call(0, env.individual_orderbook_spending_cap_by_need, buyer, good, price_index, need_kind, need_amount)))
        willingness = 0
        if hasattr(env, "individual_effective_buy_willingness"):
            willingness_tuple = _safe_call((0, 0, 0), env.individual_effective_buy_willingness, buyer, good, need_kind)
            if isinstance(willingness_tuple, (tuple, list)) and len(willingness_tuple) >= 2:
                willingness = int(willingness_tuple[1])
        available = 0
        if orders is not None and hasattr(env, "orderbook_available_amount_for_buyer"):
            available = int(max(0, _safe_call(0, env.orderbook_available_amount_for_buyer, orders, population, buyer, good)))
        out.append(DemandPlanItem(
            turn=int(getattr(env, "turn", 0)),
            buyer_type="individual",
            buyer_id=_buyer_id(buyer),
            population=str(population),
            good=good,
            need_kind=need_kind,
            priority=priority,
            need_amount=need_amount,
            available_amount=available,
            price_index=price_index,
            estimated_spending_cap=cap,
            effective_willingness=willingness,
            budget_cap_kind="individual_orderbook_spending_cap_by_need",
            allow_cross_tribe=bool(_safe_call(False, env.is_feature_enabled, "enable_global_trade")) if hasattr(env, "is_feature_enabled") else False,
        ))
    return out


def build_government_demand_plan(env: Any, population: str, orders: Optional[Dict[str, list]] = None) -> List[DemandPlanItem]:
    """Build a plain demand plan for the government last-buyer path.

    Government demand is intentionally approximate at this stage: it records the
    remaining target-stock gap and spending cap per good. The exact live purchase
    order still stays in ``Environment.government_orderbook_purchase_phase``.
    """
    out: List[DemandPlanItem] = []
    if hasattr(env, "is_feature_enabled") and not env.is_feature_enabled("enable_government_orderbook_buyer"):
        return out
    for good in TRADED_GOODS:
        current = int(max(0, _safe_call(0, env.government_good_stock, population, good))) if hasattr(env, "government_good_stock") else 0
        target = int(max(0, _safe_call(0, env.government_target_stock_amount, population, good))) if hasattr(env, "government_target_stock_amount") else 0
        need = max(0, target - current)
        if need <= 0 and orders:
            # Last-buyer mode can still absorb leftovers when deposit and willingness allow it.
            need = sum(int(o.get("amount", 0) or 0) for o in orders.get(good, []) if int(o.get("amount", 0) or 0) > 0)
        if need <= 0:
            continue
        price_index = int(max(1, _safe_call(1, env.goods_price_index, population, good))) if hasattr(env, "goods_price_index") else 1
        cap = int(max(0, _safe_call(0, env.government_orderbook_spending_cap, population, good, price_index))) if hasattr(env, "government_orderbook_spending_cap") else 0
        cfg = getattr(env, "state", {}).get("population_config", {}).get(population, {}) if hasattr(env, "state") else {}
        willingness = int(max(0, min(100, int(cfg.get("government_buy_willingness", 60)))))
        out.append(DemandPlanItem(
            turn=int(getattr(env, "turn", 0)),
            buyer_type="government",
            buyer_id=f"Government:{population}",
            population=str(population),
            good=good,
            need_kind="government_target_or_last_buyer",
            priority=100,
            need_amount=int(need),
            available_amount=sum(int(o.get("amount", 0) or 0) for o in (orders or {}).get(good, [])) if orders else 0,
            price_index=price_index,
            estimated_spending_cap=cap,
            effective_willingness=willingness,
            budget_cap_kind="government_orderbook_spending_cap",
            allow_cross_tribe=True,
        ))
    return out


def build_buyer_demand_plan(env: Any, orders: Optional[Dict[str, list]] = None, include_government: bool = True) -> List[Dict[str, Any]]:
    """Build all current buyer demand items as plain dictionaries.

    This is the centralized, audit-friendly demand plan introduced in Merged
    Package 1. It is safe to call from tools and GUI pages because it does not
    mutate buyer, company, or government state.
    """
    records: List[DemandPlanItem] = []
    for population, pop in getattr(env, "populations", {}).items():
        for buyer in list(pop):
            records.extend(build_individual_demand_plan(env, population, buyer, orders=orders))
    if include_government:
        for population in getattr(env, "population_names", []):
            records.extend(build_government_demand_plan(env, population, orders=orders))
    records.sort(key=lambda item: (item.turn, item.priority, item.buyer_type, item.population, item.buyer_id, item.good))
    return [item.to_dict() for item in records]


def summarize_demand_plan(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total_items = 0
    by_buyer_type: Dict[str, int] = {}
    by_good: Dict[str, int] = {}
    by_need_kind: Dict[str, int] = {}
    total_need_by_good: Dict[str, int] = {}
    total_cap_by_good: Dict[str, int] = {}
    for record in records:
        total_items += 1
        buyer_type = str(record.get("buyer_type", "unknown"))
        good = str(record.get("good", "unknown"))
        need_kind = str(record.get("need_kind", "unknown"))
        by_buyer_type[buyer_type] = by_buyer_type.get(buyer_type, 0) + 1
        by_good[good] = by_good.get(good, 0) + 1
        by_need_kind[need_kind] = by_need_kind.get(need_kind, 0) + 1
        total_need_by_good[good] = total_need_by_good.get(good, 0) + int(record.get("need_amount", 0) or 0)
        total_cap_by_good[good] = total_cap_by_good.get(good, 0) + int(record.get("estimated_spending_cap", 0) or 0)
    return {
        "total_items": total_items,
        "by_buyer_type": by_buyer_type,
        "by_good": by_good,
        "by_need_kind": by_need_kind,
        "total_need_by_good": total_need_by_good,
        "total_estimated_spending_cap_by_good": total_cap_by_good,
    }

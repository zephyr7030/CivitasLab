"""CivitasLab social-lifecycle science helpers.

Merged Package 6A deliberately skips the tool mechanism.  This module holds pure,
small helper functions for medical recovery, education capital, reproductive
security, company resilience, government pressure, and evolution fitness signals.
It has no dependency on model.py so the live model can keep its current object
structure while gaining a more explainable lifecycle layer.
"""
from __future__ import annotations


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def health_sickness_multiplier(health_index: float) -> float:
    """Return a bounded sickness-risk multiplier from a 0-100 health index."""
    health = clamp(float(health_index), 0.0, 100.0)
    # 100 health leaves the old risk unchanged; very poor health can at most add
    # about 60% risk, avoiding an abrupt disease/death cascade.
    return clamp(1.0 + (100.0 - health) / 160.0, 0.75, 1.60)


def labor_health_education_adjustment(health_index: float, education_capital: float) -> int:
    """Small labor-probability adjustment from health and education capital."""
    health = clamp(float(health_index), 0.0, 100.0)
    edu = max(0.0, float(education_capital))
    health_adj = int(round((health - 70.0) / 10.0))  # roughly -7..+3
    edu_bonus = int(clamp(edu / 25.0, 0.0, 8.0))
    return int(clamp(health_adj + edu_bonus, -10, 10))


def apply_health_after_survival(ind, *, food_paid: int, medical_paid: int, survival_cost: int, was_sick: bool, was_critical: bool) -> int:
    """Mutate and return an individual's health delta after survival consumption.

    Positive health comes from meeting food and medical requirements.  Shortage
    reduces health, but this helper never directly kills or creates resources;
    death/critical transitions remain in model.py.
    """
    cost = max(1, int(survival_cost))
    health = float(getattr(ind, "health_index", 100))
    delta = 0.0
    delta += 1.0 if food_paid >= cost else -min(12.0, (cost - max(0, food_paid)) / cost * 12.0)
    if was_sick:
        delta += 5.0 if medical_paid >= cost else -min(15.0, (cost - max(0, medical_paid)) / cost * 15.0)
    if was_critical:
        delta += 3.0 if food_paid >= cost and (not was_sick or medical_paid >= cost) else -8.0
    new_health = int(round(clamp(health + delta, 0.0, 100.0)))
    setattr(ind, "health_index", new_health)
    setattr(ind, "health_delta_this_turn", int(round(new_health - health)))
    if new_health < health:
        setattr(ind, "health_deteriorated_this_turn", 1)
    return int(round(new_health - health))


def medical_recovery_chance(medical_level: float, health_index: float, *, medical_paid: int, survival_cost: int, was_critical: bool = False) -> float:
    """Probability that a sick individual recovers after receiving medical goods."""
    if medical_paid < max(1, int(survival_cost)):
        return 0.0
    chance = 20.0 + clamp(medical_level, 0, 100) * 0.35 + clamp(health_index, 0, 100) * 0.20
    if was_critical:
        chance -= 15.0
    return clamp(chance, 5.0, 85.0)


def education_capital_from_child(child) -> int:
    """Current education capital proxy for a child after family/government education."""
    return max(0, int(getattr(child, "education_temp_intelligence_received", 0)))


def reproductive_security_score(ind, *, survival_cost: int, parent_food_required: int, reproduction_goods_required: int, tribe_trust: float) -> float:
    """0-100 reproductive security score used for observation and chance adjustment."""
    if getattr(ind, "critical", False) or getattr(ind, "is_sick", 0):
        return 0.0
    cost = max(1, int(survival_cost))
    food_req = max(1, int(parent_food_required))
    repro_req = max(1, int(reproduction_goods_required))
    food_ratio = clamp(float(getattr(ind, "food", 0)) / food_req, 0.0, 2.0) / 2.0
    repro_ratio = clamp(float(getattr(ind, "reproduction_goods", 0)) / repro_req, 0.0, 2.0) / 2.0
    money_ratio = clamp(float(getattr(ind, "balance", 0)) / max(1, cost * 2), 0.0, 2.0) / 2.0
    health_ratio = clamp(float(getattr(ind, "health_index", 100)) / 100.0, 0.0, 1.0)
    trust_ratio = clamp(float(tribe_trust) / 100.0, 0.0, 1.0)
    return round((food_ratio * 30 + repro_ratio * 30 + money_ratio * 15 + health_ratio * 15 + trust_ratio * 10), 4)


def reproductive_chance_with_security(base_reproduce: int, security_score: float) -> tuple[int, int]:
    """Return effective chance and small security bonus/penalty."""
    bonus = int(round((clamp(security_score, 0, 100) - 50.0) / 10.0))
    bonus = int(clamp(bonus, -5, 5))
    return int(clamp(int(base_reproduce) + bonus, 0, 100)), bonus


def company_resilience_score(*, branch_money_total: float, branch_stock_total: float, survival_cost: int, population_count: int) -> float:
    """0-100 proxy: how much cash/stock buffer the company system has."""
    need = max(1, int(survival_cost) * max(1, int(population_count)))
    cash_ratio = clamp(float(branch_money_total) / need, 0.0, 2.0) / 2.0
    stock_ratio = clamp(float(branch_stock_total) / need, 0.0, 2.0) / 2.0
    return round((cash_ratio * 45 + stock_ratio * 55), 4)


def company_strategy_bonus(*, good: str, stock: int, target: int, unmet_demand: int, survival_cost: int) -> float:
    """Small expected-profit bonus for socially important shortages, excluding tools."""
    if good == "tools":
        return 0.0
    target = max(1, int(target))
    stock_gap_ratio = clamp((target - max(0, int(stock))) / target, 0.0, 1.0)
    unmet_ratio = clamp(max(0, int(unmet_demand)) / max(1, int(survival_cost)), 0.0, 3.0) / 3.0
    importance = {"food": 1.0, "medical_goods": 0.9, "reproduction_goods": 0.75, "education_goods": 0.55}.get(good, 0.0)
    return round((stock_gap_ratio * 14 + unmet_ratio * 16) * importance, 4)


def government_policy_pressure_score(*, hard_unmet_total: float, aid_unmet_count: int, fiscal_deposit: float, survival_cost: int, population_count: int) -> float:
    """0-100 proxy: high means public policy pressure is high."""
    pop = max(1, int(population_count))
    cost = max(1, int(survival_cost))
    hard_pressure = clamp(float(hard_unmet_total) / (cost * pop), 0.0, 1.0)
    aid_pressure = clamp(float(aid_unmet_count) / pop, 0.0, 1.0)
    fiscal_buffer = clamp(float(fiscal_deposit) / (cost * pop), 0.0, 2.0) / 2.0
    return round(clamp((hard_pressure * 55 + aid_pressure * 35 + (1.0 - fiscal_buffer) * 10), 0.0, 100.0), 4)

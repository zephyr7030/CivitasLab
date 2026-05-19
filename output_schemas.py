"""BOT8 output schema helpers.

This module is a safe first step toward splitting the very large summary output into
core/market/company/government/diagnostic groups. It does not replace output.py yet;
it provides categorization and inspection utilities so future refactors can be done
with regression checks.
"""

CORE_PREFIXES = (
    "Turn", "Population", "PopCount", "Birth", "Death", "Avg", "Min", "Max",
    "Env", "ResourcePressure", "ResourceRegen", "ResourceUse", "LaborResource", "ResourceLimit",
)

MARKET_PREFIXES = (
    "Market", "FoodHard", "MedicalHard", "ReproductionHard", "HardNeed", "ReserveNeed",
    "EffectiveBuy", "WageConsumption", "WageFunded", "WorkerMarket",
)

COMPANY_PREFIXES = (
    "Company", "FoodCompany", "MedicalCompany", "EducationCompany", "ReproductionCompany",
    "ToolsCompany", "TotalWages", "AvgWage", "MedianWage", "MinWage", "Workers", "WageTo",
    "Bottom20Wage", "InventorySales", "ExcessCash", "HistoricalInventory", "FoodProduced",
    "MedicalGoodsProduced", "EducationGoodsProduced", "ReproductionGoodsProduced", "ToolsProduced",
)

GOVERNMENT_PREFIXES = (
    "Government", "FoodAid", "MedicalAid", "CriticalMedicalAid",
)

DIAGNOSTIC_MARKERS = (
    "Blocked", "OldLogic", "WhenPopBelow", "Last", "LowPop", "SingleSurvivor",
    "Gini", "Bottom20", "ZeroCount", "BelowSurvival", "Critical", "NoWorker", "Snapshot",
    "Eligible", "Unmet", "Unsatisfied", "SatisfiedRate", "Gap", "Pressure",
)


def categorize_field(field_name: str) -> str:
    """Return the recommended output group for a summary field."""
    if field_name.startswith(GOVERNMENT_PREFIXES):
        return "government"
    if field_name.startswith(COMPANY_PREFIXES):
        return "company"
    if field_name.startswith(MARKET_PREFIXES):
        return "market"
    if any(marker in field_name for marker in DIAGNOSTIC_MARKERS):
        return "diagnostics"
    if field_name.startswith(CORE_PREFIXES):
        return "summary_core"
    return "diagnostics"


def build_schema_groups(summary_headers):
    groups = {
        "summary_core": [],
        "market": [],
        "company": [],
        "government": [],
        "diagnostics": [],
    }
    for field in summary_headers:
        groups[categorize_field(field)].append(field)
    return groups


def schema_stats(summary_headers):
    groups = build_schema_groups(summary_headers)
    return {name: len(fields) for name, fields in groups.items()}

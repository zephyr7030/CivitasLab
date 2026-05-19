import os, json, copy
from config import DEFAULT_SETTINGS, DEFAULT_POPULATION_CONFIG, POP_LABELS, MAX_POPULATION_TYPES, SETTINGS_FILE, PARAM_RANGES

def get_active_population_names(settings):
    count = int(settings["base"].get("population_count", 3))
    return POP_LABELS[:max(1, min(3, count))]

def get_param_range(path):
    if path in PARAM_RANGES:
        return PARAM_RANGES[path]
    if path.startswith("population."):
        param = path.split(".")[-1]
        return {"morality":(0,100),"strength":(0,100000),"reproduce":(0,100),"labor":(0,100),"initial_env_resource":(0,10**12),"resource_regen":(0,10**12),"env_capacity":(0,10**12),"env_health":(0,100),"env_degradation_rate":(0,100),"env_recovery_rate":(0,100),"security":(0,100),"medical_level":(0,100),"trust":(0,100),"gov_aid_budget_ratio":(0,100),"labor_tax_rate":(0,100),"wealth_tax_exempt_threshold":(0,10**12),"wealth_tax_threshold":(0,10**12),"wealth_tax_low_rate":(0,100),"wealth_tax_rate":(0,100),"import_tax_rate":(0,50),"trade_tax_rate":(0,50),"market_control_budget_ratio":(0,100),"food_subsidy_rate":(0,100),"medical_subsidy_rate":(0,100),"company_initial_money":(0,10**12),"use_population_scaled_initials":(0,1),"company_initial_money_per_capita":(0,10**12),"government_initial_money_per_capita":(0,10**12),"government_initial_food_rounds":(0,100),"government_initial_medical_goods_ratio":(0,1000),"government_initial_education_goods_ratio":(0,1000),"government_initial_reproduction_goods_ratio":(0,1000),"company_initial_food_rounds":(0,100),"company_initial_medical_goods_ratio":(0,1000),"company_initial_education_goods_ratio":(0,1000),"company_initial_reproduction_goods_ratio":(0,1000),"enable_repro_education_inventory_resilience":(0,1),"repro_inventory_target_births_ratio":(0,1000),"education_inventory_target_births_ratio":(0,1000),"repro_education_inventory_resilience_weight":(0,1000),"company_production_tendency":(0,100),"labor_reward_ratio":(0,100),"enable_wage_responsive_consumption":(0,1),"wage_consumption_bonus_per_survival":(0,100),"wage_consumption_bonus_cap":(0,100),"individual_buy_willingness":(0,100),"government_buy_willingness":(0,100),"gov_education_enabled":(0,1),"gov_education_budget_ratio":(0,100),"gov_education_temp_int_per_100":(0,100000)}.get(param)
    return None

def range_text(path):
    r = get_param_range(path)
    return "范围：True / False" if r is None else f"范围：{r[0]} - {r[1]}"

def deep_update(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base

def normalize_settings(settings):
    settings.setdefault("base", {})
    # dev11：教育临时智慧参数从“每100存款”改为“每100教育用品”。旧设置自动迁移。
    if "education_temp_int_per_100_balance" in settings["base"] and "education_temp_int_per_100_goods" not in settings["base"]:
        settings["base"]["education_temp_int_per_100_goods"] = settings["base"].get("education_temp_int_per_100_balance", 10)
    settings["base"].setdefault("population_count", 1)
    settings["base"]["population_count"] = max(1, min(3, int(settings["base"]["population_count"])))
    # dev11：删除商品经济一致性修复中不再使用的旧全局参数。
    for obsolete in [
        "chart_refresh_interval", "reproduce_cost", "resource_allocation_mode",
        "equal_resource_ratio", "ability_resource_ratio",
        "shared_equal_ratio", "shared_need_ratio", "shared_ability_ratio",
        "education_temp_int_per_100_balance", "labor_self_cost", "initial_reproduce",
    ]:
        settings["base"].pop(obsolete, None)
    settings.setdefault("switches", {})
    for k, v in DEFAULT_SETTINGS.get("switches", {}).items():
        settings["switches"].setdefault(k, v)
    settings.setdefault("population", {})
    for p in POP_LABELS:
        settings["population"].setdefault(p, copy.deepcopy(DEFAULT_POPULATION_CONFIG[p]))
        for k, v in DEFAULT_POPULATION_CONFIG[p].items():
            settings["population"][p].setdefault(k, v)
    if "switches" in settings and "enable_charity" in settings["switches"] and "enable_government_aid" not in settings["switches"]:
        settings["switches"]["enable_government_aid"] = settings["switches"]["enable_charity"]

    # 机制调度兼容与补全。
    settings.setdefault("switch_schedules", {})
    for switch_key in settings.get("switches", {}):
        settings["switch_schedules"].setdefault(switch_key, {"enable_rounds": "", "disable_rounds": ""})
        settings["switch_schedules"][switch_key].setdefault("enable_rounds", "")
        settings["switch_schedules"][switch_key].setdefault("disable_rounds", "")

    # dev31：补全新增基础参数，避免旧设置文件缺少小族群初始条件参数时出现 KeyError。
    for k, v in DEFAULT_SETTINGS.get("base", {}).items():
        settings["base"].setdefault(k, v)

    return settings

def load_settings():
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                deep_update(settings, json.load(f))
        except Exception:
            pass
    return normalize_settings(settings)

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(normalize_settings(settings), f, ensure_ascii=False, indent=4)

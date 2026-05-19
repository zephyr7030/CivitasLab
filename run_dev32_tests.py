import copy, random, json, statistics
from collections import Counter
import config
from model import Environment

SEEDS = [20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88]


def make_cfg(max_turns=100, init_pop=10, initial_reproduce=None, orderbook_buyer=True, macro_control=True, small_group_initial=True, gov_repro_release=False):
    cfg = copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns'] = max_turns
    cfg['base']['initial_population'] = init_pop
    cfg['base']['population_count'] = 1
    cfg['base']['enable_small_group_initial_conditions'] = small_group_initial
    cfg['base']['enable_government_reproduction_goods_release'] = gov_repro_release
    cfg['switches']['enable_government_orderbook_buyer'] = orderbook_buyer
    cfg['switches']['enable_government_macro_control'] = macro_control
    if initial_reproduce is not None:
        for p in cfg['population']:
            cfg['population'][p]['reproduce'] = initial_reproduce
    return cfg


def run_one(seed, max_turns=100, init_pop=10, initial_reproduce=None, orderbook_buyer=True, macro_control=True, small_group_initial=True, gov_repro_release=False):
    random.seed(seed)
    cfg = make_cfg(max_turns, init_pop, initial_reproduce, orderbook_buyer, macro_control, small_group_initial, gov_repro_release)
    env = Environment(cfg)
    init_money = sum(ind.balance for pop in env.populations.values() for ind in pop) + sum(env.government_deposit.values()) + sum(env.company_totals(p)['money'] for p in env.population_names)
    death_reasons = Counter()
    rows = []
    for _ in range(max_turns):
        ok = env.run_turn()
        for p, ind in env.dead_individuals_this_turn:
            death_reasons[ind.death_reason] += 1
        if env.current_summary_rows:
            rows.append(env.current_summary_rows[0])
        if not ok:
            break
    final_pop = sum(len(pop) for pop in env.populations.values())
    final_money = sum(ind.balance for pop in env.populations.values() for ind in pop) + sum(env.government_deposit.values()) + sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(col): return sum(int(r.get(col, 0) or 0) for r in rows)
    def avgcol(col):
        vals = [float(r.get(col, 0) or 0) for r in rows]
        return round(statistics.mean(vals), 4) if vals else 0
    pops = [int(r.get('PopCount', 0) or 0) for r in rows]
    last_birth_turn = 0
    for r in rows:
        if int(r.get('BirthCount', 0) or 0) > 0:
            last_birth_turn = int(r.get('Turn', 0) or 0)
    last = rows[-1] if rows else {}
    tail = rows[-10:] if rows else []
    return {
        'seed': seed,
        'turns_run': env.turn,
        'survived': env.turn >= max_turns and final_pop > 0,
        'extinction_turn': None if final_pop > 0 else env.turn,
        'final_pop': final_pop,
        'peak_pop': max(pops) if pops else init_pop,
        'avg_pop': round(sum(pops)/len(pops),2) if pops else 0,
        'min_positive_pop': min([p for p in pops if p>0], default=0),
        'turns_pop_below5': sum(1 for p in pops if 0 < p < 5),
        'total_births': env.cumulative_birth_count.get('A',0),
        'total_deaths': env.cumulative_death_count.get('A',0),
        'last_birth_turn': last_birth_turn,
        'death_reasons': dict(death_reasons),
        'birth_block_low_reproduce': env.cumulative_birth_blocked_low_reproduce_chance.get('A',0),
        'birth_block_no_reproduction_goods': env.cumulative_birth_blocked_no_reproduction_goods.get('A',0),
        'birth_block_no_food_safety': env.cumulative_birth_blocked_no_food_safety.get('A',0),
        'birth_block_sick': env.cumulative_birth_blocked_sick.get('A',0),
        'birth_block_critical': env.cumulative_birth_blocked_critical.get('A',0),
        'entered_critical_when_below5': sumcol('EnteredCriticalWhenPopulationBelow5'),
        'recovered_critical_when_below5': sumcol('RecoveredCriticalWhenPopulationBelow5'),
        'deaths_life_end_below3': sumcol('DeathsByLifeEndWhenPopulationBelow3'),
        'deaths_life_end_below5': sumcol('DeathsByLifeEndWhenPopulationBelow5'),
        'deaths_food_shortage_below5': sumcol('DeathsByFoodShortageWhenPopulationBelow5'),
        'deaths_medical_shortage_below5': sumcol('DeathsByMedicalShortageWhenPopulationBelow5'),
        'deaths_critical_goods_shortage_below5': sumcol('DeathsByCriticalGoodsShortageWhenPopulationBelow5'),
        'avg_life_remaining': avgcol('AvgLifeRemaining'),
        'min_life_remaining_tail': min([int(r.get('MinLifeRemaining',0) or 0) for r in tail], default=0),
        'avg_age_round': avgcol('AvgAgeRound'),
        'workers_when_below5': sumcol('WorkersWhenPopulationBelow5'),
        'wage_when_below5': sumcol('WagePaidWhenPopulationBelow5'),
        'food_bought_when_below5': sumcol('FoodBoughtWhenPopulationBelow5'),
        'company_food_stock_when_below5_avg': avgcol('CompanyFoodStockWhenPopulationBelow5'),
        'government_food_when_below5_avg': avgcol('GovernmentFoodWhenPopulationBelow5'),
        'gov_reproduction_goods_released': sumcol('GovernmentReproductionGoodsReleased'),
        'gov_surplus_reproduction_deleted': sumcol('GovernmentSurplusReproductionGoodsDeleted'),
        'government_orderbook_spending': sumcol('GovernmentOrderbookPurchaseSpending'),
        'government_surplus_value': sumcol('GovernmentSurplusValueTotal'),
        'market_food_volume': sumcol('MarketFoodVolume'),
        'market_reproduction_goods_volume': sumcol('MarketReproductionGoodsVolume'),
        'reproduction_hard_demand_total': sumcol('ReproductionGoodsHardDemandTotal'),
        'reproduction_hard_satisfied': sumcol('ReproductionGoodsHardDemandSatisfied'),
        'reproduction_hard_unsatisfied': sumcol('ReproductionGoodsHardDemandUnsatisfied'),
        'single_survivor_turn_count': int(last.get('SingleSurvivorTurnCount', 0) or 0),
        'turns_at_population_below3': int(last.get('TurnsAtPopulationBelow3', 0) or 0),
        'last_survivor_death_reason': str(last.get('LastSurvivorDeathReason', '')),
        'last_survivor_reproduce_chance_failed': int(last.get('LastSurvivorReproduceChanceFailed', 0) or 0),
        'last_survivor_had_reproduction_goods': int(last.get('LastSurvivorHadReproductionGoods', 0) or 0),
        'last_survivor_had_food_for_birth': int(last.get('LastSurvivorHadFoodForBirth', 0) or 0),
        'money_delta': final_money - init_money,
        'final_individual_money': sum(ind.balance for pop in env.populations.values() for ind in pop),
        'final_company_money': sum(env.company_totals(p)['money'] for p in env.population_names),
        'final_government_money': sum(env.government_deposit.values()),
        'final_company_stock': sum(env.company_totals(p)['stock'] for p in env.population_names),
        'tail': tail,
    }


def run_suite(max_turns=100, init_pop=10, initial_reproduce=None, orderbook_buyer=True, macro_control=True, small_group_initial=True, gov_repro_release=False):
    results = [run_one(seed, max_turns, init_pop, initial_reproduce, orderbook_buyer, macro_control, small_group_initial, gov_repro_release) for seed in SEEDS]
    agg_deaths = Counter()
    for r in results:
        agg_deaths.update(r['death_reasons'])
    ext_turns = [r['extinction_turn'] for r in results if r['extinction_turn']]
    def mean(key): return round(statistics.mean([r[key] for r in results]), 2)
    summary = {
        'max_turns': max_turns,
        'init_pop': init_pop,
        'initial_reproduce': initial_reproduce if initial_reproduce is not None else config.DEFAULT_POPULATION_CONFIG['A']['reproduce'],
        'orderbook_buyer': orderbook_buyer,
        'macro_control': macro_control,
        'small_group_initial': small_group_initial,
        'gov_repro_release': gov_repro_release,
        'survival_count': sum(1 for r in results if r['survived']),
        'extinction_count': sum(1 for r in results if not r['survived']),
        'avg_extinction_turn': round(statistics.mean(ext_turns),2) if ext_turns else None,
        'median_extinction_turn': statistics.median(ext_turns) if ext_turns else None,
        'avg_final_pop': mean('final_pop'),
        'avg_pop': mean('avg_pop'),
        'avg_births': mean('total_births'),
        'avg_deaths': mean('total_deaths'),
        'aggregate_death_reasons': dict(agg_deaths),
        'avg_block_low_reproduce': mean('birth_block_low_reproduce'),
        'avg_block_no_reproduction_goods': mean('birth_block_no_reproduction_goods'),
        'avg_block_no_food_safety': mean('birth_block_no_food_safety'),
        'avg_entered_critical_when_below5': mean('entered_critical_when_below5'),
        'avg_recovered_critical_when_below5': mean('recovered_critical_when_below5'),
        'avg_deaths_life_end_below3': mean('deaths_life_end_below3'),
        'avg_deaths_life_end_below5': mean('deaths_life_end_below5'),
        'avg_deaths_critical_goods_shortage_below5': mean('deaths_critical_goods_shortage_below5'),
        'avg_workers_when_below5': mean('workers_when_below5'),
        'avg_wage_when_below5': mean('wage_when_below5'),
        'avg_food_bought_when_below5': mean('food_bought_when_below5'),
        'avg_turns_pop_below5': mean('turns_pop_below5'),
        'avg_single_survivor_turn_count': mean('single_survivor_turn_count'),
        'avg_turns_below3': mean('turns_at_population_below3'),
        'max_abs_money_delta': max(abs(r['money_delta']) for r in results),
        'avg_market_reproduction_goods_volume': mean('market_reproduction_goods_volume'),
        'avg_reproduction_hard_satisfied': mean('reproduction_hard_satisfied'),
        'avg_reproduction_hard_unsatisfied': mean('reproduction_hard_unsatisfied'),
    }
    return {'summary': summary, 'results': results}


if __name__ == '__main__':
    payload = {
        'baseline_repro50_10p_100': run_suite(100, 10, 50),
        'baseline_repro50_10p_1000': run_suite(1000, 10, 50),
        'baseline_repro50_5p_1000': run_suite(1000, 5, 50),
        'repro60_10p_100': run_suite(100, 10, 60),
        'repro60_10p_1000': run_suite(1000, 10, 60),
        'repro60_5p_1000': run_suite(1000, 5, 60),
        'repro65_10p_1000': run_suite(1000, 10, 65),
        'repro65_5p_1000': run_suite(1000, 5, 65),
    }
    with open('BOT8_dev32_CHECK_RESULTS.json', 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps({k:v['summary'] for k,v in payload.items()}, ensure_ascii=False, indent=2))

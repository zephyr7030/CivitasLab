import copy, random, json, statistics
from collections import Counter
import config
from model import Environment, TRADED_GOODS, GOOD_FIELDS

SEEDS = [20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88]

def run_one(seed, max_turns=100, init_pop=10, macro_control=True):
    random.seed(seed)
    cfg = copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns'] = max_turns
    cfg['base']['initial_population'] = init_pop
    cfg['base']['population_count'] = 1
    cfg['switches']['enable_government_macro_control'] = macro_control
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
        return round(sum(vals)/len(vals), 3) if vals else 0
    pops = [int(r.get('PopCount', 0) or 0) for r in rows]
    last_birth_turn = 0
    for r in rows:
        if int(r.get('BirthCount', 0) or 0) > 0:
            last_birth_turn = int(r.get('Turn', 0) or 0)
    return {
        'seed': seed,
        'turns_run': env.turn,
        'survived': env.turn >= max_turns and final_pop > 0,
        'extinction_turn': None if final_pop > 0 else env.turn,
        'final_pop': final_pop,
        'peak_pop': max(pops) if pops else init_pop,
        'avg_pop': round(sum(pops)/len(pops),2) if pops else 0,
        'min_positive_pop': min([p for p in pops if p>0], default=0),
        'total_births': env.cumulative_birth_count.get('A',0),
        'total_deaths': env.cumulative_death_count.get('A',0),
        'last_birth_turn': last_birth_turn,
        'death_reasons': dict(death_reasons),
        'birth_block_low_reproduce': env.cumulative_birth_blocked_low_reproduce_chance.get('A',0),
        'birth_block_no_reproduction_goods': env.cumulative_birth_blocked_no_reproduction_goods.get('A',0),
        'birth_block_no_food_safety': env.cumulative_birth_blocked_no_food_safety.get('A',0),
        'birth_block_sick': env.cumulative_birth_blocked_sick.get('A',0),
        'birth_block_critical': env.cumulative_birth_blocked_critical.get('A',0),
        'company_inventory_listed': sumcol('CompanyInventoryListed'),
        'company_sold_individuals': sumcol('CompanyInventorySoldToIndividuals'),
        'company_sold_government': sumcol('CompanyInventorySoldToGovernment'),
        'company_unsold': sumcol('CompanyInventoryUnsold'),
        'company_goods_produced': sumcol('CompanyGoodsProduced'),
        'company_wage_paid': sumcol('CompanyWagePaid'),
        'company_sales_income': sumcol('CompanySalesIncome'),
        'government_orderbook_spending': sumcol('GovernmentOrderbookPurchaseSpending'),
        'government_surplus_value': sumcol('GovernmentSurplusValueTotal'),
        'market_food_volume': sumcol('MarketFoodVolume'),
        'market_reproduction_goods_volume': sumcol('MarketReproductionGoodsVolume'),
        'reproduction_hard_demand_total': sumcol('ReproductionGoodsHardDemandTotal'),
        'reproduction_hard_satisfied': sumcol('ReproductionGoodsHardDemandSatisfied'),
        'reproduction_hard_unsatisfied': sumcol('ReproductionGoodsHardDemandUnsatisfied'),
        'reproduction_block_no_stock': sumcol('ReproductionGoodsBlockedNoCompanyStock'),
        'reproduction_block_no_money': sumcol('ReproductionGoodsBlockedNoMoney'),
        'avg_market_stability': avgcol('MarketStabilityIndex'),
        'final_individual_money': sum(ind.balance for pop in env.populations.values() for ind in pop),
        'final_company_money': sum(env.company_totals(p)['money'] for p in env.population_names),
        'final_government_money': sum(env.government_deposit.values()),
        'money_delta': final_money - init_money,
        'final_company_stock': sum(env.company_totals(p)['stock'] for p in env.population_names),
        'tail': rows[-5:],
    }

def run_suite(max_turns=100, macro_control=True):
    results = [run_one(seed, max_turns=max_turns, macro_control=macro_control) for seed in SEEDS]
    agg_deaths = Counter()
    for r in results:
        agg_deaths.update(r['death_reasons'])
    ext_turns = [r['extinction_turn'] for r in results if r['extinction_turn']]
    summary = {
        'max_turns': max_turns,
        'macro_control': macro_control,
        'survival_count': sum(1 for r in results if r['survived']),
        'extinction_count': sum(1 for r in results if not r['survived']),
        'avg_extinction_turn': round(statistics.mean(ext_turns),2) if ext_turns else None,
        'median_extinction_turn': statistics.median(ext_turns) if ext_turns else None,
        'avg_final_pop': round(statistics.mean([r['final_pop'] for r in results]),2),
        'avg_births': round(statistics.mean([r['total_births'] for r in results]),2),
        'avg_deaths': round(statistics.mean([r['total_deaths'] for r in results]),2),
        'aggregate_death_reasons': dict(agg_deaths),
        'avg_block_low_reproduce': round(statistics.mean([r['birth_block_low_reproduce'] for r in results]),2),
        'avg_block_no_reproduction_goods': round(statistics.mean([r['birth_block_no_reproduction_goods'] for r in results]),2),
        'avg_block_no_food_safety': round(statistics.mean([r['birth_block_no_food_safety'] for r in results]),2),
        'max_abs_money_delta': max(abs(r['money_delta']) for r in results),
        'avg_market_food_volume': round(statistics.mean([r['market_food_volume'] for r in results]),2),
        'avg_market_reproduction_goods_volume': round(statistics.mean([r['market_reproduction_goods_volume'] for r in results]),2),
        'avg_reproduction_hard_satisfied': round(statistics.mean([r['reproduction_hard_satisfied'] for r in results]),2),
        'avg_reproduction_hard_unsatisfied': round(statistics.mean([r['reproduction_hard_unsatisfied'] for r in results]),2),
        'avg_government_orderbook_spending': round(statistics.mean([r['government_orderbook_spending'] for r in results]),2),
    }
    return {'summary': summary, 'results': results}

if __name__ == '__main__':
    payload = {
        'test_100': run_suite(100, macro_control=True),
        'test_1000': run_suite(1000, macro_control=True),
        'macro_off_smoke_100': run_suite(100, macro_control=False),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

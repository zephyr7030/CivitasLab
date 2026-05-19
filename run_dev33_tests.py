import copy, random, json, statistics
from collections import Counter
import config
from model import Environment

SEEDS = [20260517, 1, 2, 3, 42, 100, 999, 2026, 17, 88]

def make_cfg(max_turns=100, init_pop=10, secondary=True, secondary_ratio=50):
    cfg = copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns'] = max_turns
    cfg['base']['initial_population'] = init_pop
    cfg['base']['population_count'] = 1
    cfg['base']['enable_secondary_birth_check'] = bool(secondary)
    cfg['base']['secondary_birth_chance_ratio'] = secondary_ratio
    return cfg

def run_one(seed, max_turns=100, init_pop=10, secondary=True, secondary_ratio=50, collect_rows=False):
    random.seed(seed)
    cfg = make_cfg(max_turns, init_pop, secondary, secondary_ratio)
    env = Environment(cfg)
    init_money = sum(ind.balance for pop in env.populations.values() for ind in pop) + sum(env.government_deposit.values()) + sum(env.company_totals(p)['money'] for p in env.population_names)
    death_reasons = Counter()
    rows = []
    details=[]
    for _ in range(max_turns):
        ok = env.run_turn()
        for p, ind in env.dead_individuals_this_turn:
            death_reasons[ind.death_reason] += 1
        if env.current_summary_rows:
            row=env.current_summary_rows[0]
            rows.append(row)
            if collect_rows:
                pop=env.populations['A']
                def vals(attr): return [getattr(ind, attr, 0) for ind in pop]
                def stat(xs):
                    if not xs:
                        return {'sum':0,'avg':0,'min':0,'max':0,'values':[]}
                    return {'sum':round(sum(xs),2),'avg':round(sum(xs)/len(xs),2),'min':round(min(xs),2),'max':round(max(xs),2),'values':[round(x,2) for x in xs]}
                details.append({
                    'turn': env.turn,
                    'pop': len(pop),
                    'births': int(row.get('BirthCount',0) or 0),
                    'secondary_births': int(row.get('SecondaryBirthSuccessCount',0) or 0),
                    'deaths': int(row.get('DeathCount',0) or 0),
                    'critical': int(row.get('CriticalCount',0) or 0),
                    'food_shortage': int(row.get('FoodShortageCount',0) or 0),
                    'money': stat(vals('balance')),
                    'food': stat(vals('food')),
                    'reproduction_goods': stat(vals('reproduction_goods')),
                    'medical_goods': stat(vals('medical_goods')),
                    'company_food_stock': row.get('CompanyFoodStock', row.get('FoodBranchStock',0)),
                    'government_food': row.get('GovernmentFood',0),
                    'market_food_volume': row.get('MarketFoodVolume',0),
                    'market_reproduction_goods_volume': row.get('MarketReproductionGoodsVolume',0),
                })
        if not ok:
            break
    final_pop = sum(len(pop) for pop in env.populations.values())
    final_money = sum(ind.balance for pop in env.populations.values() for ind in pop) + sum(env.government_deposit.values()) + sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(col): return sum(int(r.get(col, 0) or 0) for r in rows)
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    last_birth_turn=0
    for r in rows:
        if int(r.get('BirthCount',0) or 0)>0:
            last_birth_turn=int(r.get('Turn',0) or 0)
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,
        'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,
        'total_births':env.cumulative_birth_count.get('A',0),'total_deaths':env.cumulative_death_count.get('A',0),
        'secondary_birth_success':sumcol('SecondaryBirthSuccessCount'),
        'secondary_birth_condition_ready':sumcol('SecondaryBirthConditionReadyCount'),
        'secondary_birth_attempt':sumcol('SecondaryBirthAttemptCount'),
        'secondary_birth_block_low_chance':sumcol('SecondaryBirthBlockedLowReproduceChance'),
        'secondary_birth_block_no_goods':sumcol('SecondaryBirthBlockedNoReproductionGoods'),
        'secondary_birth_block_no_food':sumcol('SecondaryBirthBlockedNoFoodSafety'),
        'last_birth_turn':last_birth_turn,'death_reasons':dict(death_reasons),
        'birth_block_low_reproduce':env.cumulative_birth_blocked_low_reproduce_chance.get('A',0),
        'birth_block_no_reproduction_goods':env.cumulative_birth_blocked_no_reproduction_goods.get('A',0),
        'birth_block_no_food_safety':env.cumulative_birth_blocked_no_food_safety.get('A',0),
        'money_delta':final_money-init_money,
        'final_individual_money':sum(ind.balance for pop in env.populations.values() for ind in pop),
        'final_company_money':sum(env.company_totals(p)['money'] for p in env.population_names),
        'final_government_money':sum(env.government_deposit.values()),
        'final_company_stock':sum(env.company_totals(p)['stock'] for p in env.population_names),
        'details':details if collect_rows else None,
    }

def run_suite(max_turns=100, init_pop=10, secondary=True, secondary_ratio=50):
    results=[run_one(seed,max_turns,init_pop,secondary,secondary_ratio) for seed in SEEDS]
    agg=Counter()
    for r in results: agg.update(r['death_reasons'])
    def mean(k): return round(statistics.mean([r[k] for r in results]),2)
    ext=[r['extinction_turn'] for r in results if r['extinction_turn']]
    return {'summary':{
        'max_turns':max_turns,'init_pop':init_pop,'secondary':secondary,'secondary_ratio':secondary_ratio,
        'survival_count':sum(1 for r in results if r['survived']),'extinction_count':sum(1 for r in results if not r['survived']),
        'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
        'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_pop':mean('avg_pop'),
        'avg_births':mean('total_births'),'avg_deaths':mean('total_deaths'),
        'avg_secondary_birth_success':mean('secondary_birth_success'),
        'avg_secondary_birth_condition_ready':mean('secondary_birth_condition_ready'),
        'avg_secondary_birth_attempt':mean('secondary_birth_attempt'),
        'avg_block_low_reproduce':mean('birth_block_low_reproduce'),
        'avg_block_no_reproduction_goods':mean('birth_block_no_reproduction_goods'),
        'avg_block_no_food_safety':mean('birth_block_no_food_safety'),
        'aggregate_death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in results),
    },'results':results}

if __name__=='__main__':
    payload={
        'detailed_5p_10_seed20260517': run_one(20260517,10,5,True,50,True),
        'dev33_5p_10_10seeds': run_suite(10,5,True,50),
        'dev33_10p_100_10seeds': run_suite(100,10,True,50),
        'dev33_10p_1000_10seeds': run_suite(1000,10,True,50),
        'dev33_5p_1000_10seeds': run_suite(1000,5,True,50),
        'secondary_disabled_5p_1000_10seeds': run_suite(1000,5,False,50),
        'secondary_ratio30_5p_1000_10seeds': run_suite(1000,5,True,30),
        'secondary_ratio70_5p_1000_10seeds': run_suite(1000,5,True,70),
    }
    with open('BOT8_dev33_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    for k,v in payload.items():
        if isinstance(v,dict) and 'summary' in v:
            print(k, v['summary'])
        else:
            print(k, {'final_pop':v['final_pop'],'births':v['total_births'],'secondary_births':v['secondary_birth_success'],'details_turns':len(v['details'] or [])})

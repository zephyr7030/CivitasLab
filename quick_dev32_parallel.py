import json, statistics
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from run_dev32_tests import run_one, SEEDS

SUITES = [
    ('baseline_repro50_10p_100', dict(max_turns=100, init_pop=10, initial_reproduce=50)),
    ('baseline_repro50_10p_1000', dict(max_turns=1000, init_pop=10, initial_reproduce=50)),
    ('baseline_repro50_5p_1000', dict(max_turns=1000, init_pop=5, initial_reproduce=50)),
    ('repro60_10p_100', dict(max_turns=100, init_pop=10, initial_reproduce=60)),
    ('repro60_10p_1000', dict(max_turns=1000, init_pop=10, initial_reproduce=60)),
    ('repro60_5p_1000', dict(max_turns=1000, init_pop=5, initial_reproduce=60)),
]

def summarize(name, kwargs, results):
    agg_deaths=Counter()
    for r in results: agg_deaths.update(r['death_reasons'])
    ext=[r['extinction_turn'] for r in results if r['extinction_turn']]
    def mean(key): return round(statistics.mean([r[key] for r in results]),2)
    return {
        'max_turns': kwargs['max_turns'], 'init_pop': kwargs['init_pop'], 'initial_reproduce': kwargs['initial_reproduce'],
        'survival_count': sum(1 for r in results if r['survived']),
        'extinction_count': sum(1 for r in results if not r['survived']),
        'avg_extinction_turn': round(statistics.mean(ext),2) if ext else None,
        'median_extinction_turn': statistics.median(ext) if ext else None,
        'avg_final_pop': mean('final_pop'), 'avg_pop': mean('avg_pop'),
        'avg_births': mean('total_births'), 'avg_deaths': mean('total_deaths'),
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
        'avg_reproduction_hard_satisfied': mean('reproduction_hard_satisfied'),
        'avg_reproduction_hard_unsatisfied': mean('reproduction_hard_unsatisfied'),
    }

if __name__=='__main__':
    payload={}
    with ProcessPoolExecutor(max_workers=6) as ex:
        futs={}
        for name, kwargs in SUITES:
            for seed in SEEDS:
                fut=ex.submit(run_one, seed, **kwargs)
                futs[fut]=(name, kwargs, seed)
        by={name:[] for name,_ in SUITES}
        suite_kwargs={name:kwargs for name,kwargs in SUITES}
        for fut in as_completed(futs):
            name, kwargs, seed=futs[fut]
            by[name].append(fut.result())
    for name, kwargs in SUITES:
        results=sorted(by[name], key=lambda r: SEEDS.index(r['seed']))
        payload[name]={'summary':summarize(name, kwargs, results), 'results':results}
    with open('BOT8_dev32_CHECK_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(json.dumps({k:v['summary'] for k,v in payload.items()}, ensure_ascii=False, indent=2))

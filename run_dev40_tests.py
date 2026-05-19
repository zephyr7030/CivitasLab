import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(max_turns=1000, init_pop=5):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=False
    cfg['base']['enable_excess_cash_dividend']=False
    return cfg

def run_one(args):
    seed,max_turns,init_pop=args
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop)
    env=Environment(cfg)
    init_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    rows=[]; death=Counter()
    for _ in range(max_turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn:
            death[ind.death_reason]+=1
        if env.current_summary_rows:
            rows.append(dict(env.current_summary_rows[0]))
        if not ok:
            break
    final_pop=sum(len(pop) for pop in env.populations.values())
    final_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    def avg_col(k):
        xs=[float(r.get(k,0) or 0) for r in rows]
        return round(sum(xs)/len(xs),4) if xs else 0
    def sum_col(k):
        return round(sum(float(r.get(k,0) or 0) for r in rows),4)
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,
        'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,
        'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'death_reasons':dict(death),
        'money_delta':final_money-init_money,
        'food_shortage':sum_col('FoodShortageCount'),
        'medical_shortage':sum_col('MedicalShortageCount'),
        'critical_entered':sum_col('EnteredCriticalCount'),
        'birth_blocked_food_safety':sum_col('BirthBlockedNoFoodSafety'),
        'birth_blocked_no_repro_goods':sum_col('BirthBlockedNoReproductionGoods'),
        'birth_blocked_low_chance':sum_col('BirthBlockedLowReproduceChance'),
        'food_hard_satisfied_rate_avg':avg_col('FoodHardNeedSatisfiedRate'),
        'medical_hard_satisfied_rate_avg':avg_col('MedicalHardNeedSatisfiedRate'),
        'reproduction_hard_satisfied_rate_avg':avg_col('ReproductionHardNeedSatisfiedRate'),
        'hard_spending_total':sum_col('HardNeedSpendingTotal'),
        'reserve_spending_total':sum_col('ReserveNeedSpendingTotal'),
        'hard_blocked_no_cash':sum_col('HardNeedBlockedByNoCash'),
        'hard_blocked_no_stock':sum_col('HardNeedBlockedByNoMarketStock'),
        'hard_blocked_high_price':sum_col('HardNeedBlockedByHighPrice'),
        'hard_blocked_budget':sum_col('HardNeedBlockedByBudgetCap'),
        'wage_funded_spending':sum_col('WageFundedMarketSpending'),
        'worker_market_spending_to_company':sum_col('WorkerMarketSpendingToCompany'),
        'company_actual_revenue':sum_col('CompanyActualRevenue'),
        'market_volume':sum_col('MarketTradeVolume'),
        'food_zero_sum':sum_col('FoodZeroCount'),
        'money_zero_sum':sum_col('MoneyZeroCount'),
        'final_tail': rows[-20:] if rows else [],
    }

def suite(label,max_turns,init_pop,seeds=SEEDS):
    args=[(s,max_turns,init_pop) for s in seeds]
    with mp.Pool(processes=min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    ext=[r['extinction_turn'] for r in res if r['extinction_turn']]
    deaths=Counter()
    for r in res: deaths.update(r['death_reasons'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {'label':label,'settings':{'max_turns':max_turns,'init_pop':init_pop},'summary':{
        'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),
        'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
        'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),
        'death_reasons':dict(deaths),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),
        'avg_food_shortage':mean('food_shortage'),'avg_medical_shortage':mean('medical_shortage'),'avg_critical_entered':mean('critical_entered'),
        'avg_birth_blocked_food_safety':mean('birth_blocked_food_safety'),
        'avg_birth_blocked_no_repro_goods':mean('birth_blocked_no_repro_goods'),
        'avg_birth_blocked_low_chance':mean('birth_blocked_low_chance'),
        'avg_food_hard_satisfied_rate':mean('food_hard_satisfied_rate_avg'),
        'avg_medical_hard_satisfied_rate':mean('medical_hard_satisfied_rate_avg'),
        'avg_reproduction_hard_satisfied_rate':mean('reproduction_hard_satisfied_rate_avg'),
        'avg_hard_spending_total':mean('hard_spending_total'),'avg_reserve_spending_total':mean('reserve_spending_total'),
        'avg_hard_blocked_no_cash':mean('hard_blocked_no_cash'),'avg_hard_blocked_no_stock':mean('hard_blocked_no_stock'),
        'avg_hard_blocked_high_price':mean('hard_blocked_high_price'),'avg_hard_blocked_budget':mean('hard_blocked_budget'),
        'avg_wage_funded_spending':mean('wage_funded_spending'),
        'avg_worker_market_spending_to_company':mean('worker_market_spending_to_company'),
        'avg_company_actual_revenue':mean('company_actual_revenue'),'avg_market_volume':mean('market_volume'),
        'avg_food_zero_sum':mean('food_zero_sum'),'avg_money_zero_sum':mean('money_zero_sum'),
    },'results':res}

if __name__=='__main__':
    payload=[]
    for max_turns,init_pop in [(10,5),(100,5),(1000,5),(100,10),(1000,10)]:
        result=suite(f'dev40_{init_pop}p_{max_turns}',max_turns,init_pop)
        payload.append(result)
        print(result['label'], result['summary'])
    with open('BOT8_dev40_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)

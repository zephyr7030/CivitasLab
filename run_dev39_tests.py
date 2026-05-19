import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(max_turns=1000, init_pop=5, labor_reward_ratio=None, company_initial_money=None, wage_resp=True, bonus_per=10, bonus_cap=20):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=False
    cfg['base']['enable_excess_cash_dividend']=False
    for p,c in cfg['population'].items():
        if labor_reward_ratio is not None:
            c['labor_reward_ratio']=labor_reward_ratio
        if company_initial_money is not None:
            c['company_initial_money']=company_initial_money
        c['enable_wage_responsive_consumption']=1 if wage_resp else 0
        c['wage_consumption_bonus_per_survival']=bonus_per
        c['wage_consumption_bonus_cap']=bonus_cap
    return cfg

def run_one(args):
    seed,max_turns,init_pop,variant=args
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop,**variant)
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
    last=rows[-1] if rows else {}
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,
        'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,
        'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'death_reasons':dict(death),
        'money_delta':final_money-init_money,
        'avg_wage':avg_col('AvgWagePerWorker'),'total_wages':sum_col('TotalWagesPaid'),
        'avg_eff_buy_willingness':avg_col('EffectiveBuyWillingnessAvg'),
        'avg_wage_bonus':avg_col('WageConsumptionBonusAvg'),
        'wage_extra_cap_total':sum_col('WageResponsiveExtraCapTotal'),
        'wage_funded_spending':sum_col('WageFundedMarketSpending'),
        'worker_market_spending':sum_col('WorkerMarketSpending'),
        'worker_market_spending_to_company':sum_col('WorkerMarketSpendingToCompany'),
        'company_actual_revenue':sum_col('CompanyActualRevenue'),
        'market_volume':sum_col('MarketTradeVolume'),
        'avg_company_cash_after_wages':avg_col('CompanyCashAfterWages'),
        'avg_company_cash_after_resource':avg_col('CompanyCashAfterResourcePurchase'),
        'unable_full_wages':sum_col('CompanyUnableToPayFullWagesCount'),
        'stopped_cash':sum_col('CompanyProductionStoppedByCashCount'),
        'stopped_stock':sum_col('CompanyProductionStoppedByStockCount'),
        'food_zero_sum':sum_col('FoodZeroCount'),
        'money_zero_sum':sum_col('MoneyZeroCount'),
        'birth_blocked_food_safety':sum_col('BirthBlockedNoFoodSafety'),
        'birth_blocked_no_repro_goods':sum_col('BirthBlockedNoReproductionGoods'),
        'birth_blocked_low_chance':sum_col('BirthBlockedLowReproduceChance'),
        'final_tail': rows[-20:] if rows else [],
    }

def suite(label,max_turns,init_pop,variant,seeds=SEEDS):
    args=[(s,max_turns,init_pop,variant) for s in seeds]
    with mp.Pool(processes=min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    ext=[r['extinction_turn'] for r in res if r['extinction_turn']]
    deaths=Counter()
    for r in res: deaths.update(r['death_reasons'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {'label':label,'variant':variant,'settings':{'max_turns':max_turns,'init_pop':init_pop},'summary':{
        'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),
        'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
        'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),
        'death_reasons':dict(deaths),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),
        'avg_wage':mean('avg_wage'),'avg_total_wages':mean('total_wages'),
        'avg_eff_buy_willingness':mean('avg_eff_buy_willingness'),'avg_wage_bonus':mean('avg_wage_bonus'),
        'avg_wage_extra_cap_total':mean('wage_extra_cap_total'),'avg_wage_funded_spending':mean('wage_funded_spending'),
        'avg_worker_market_spending':mean('worker_market_spending'),'avg_worker_market_spending_to_company':mean('worker_market_spending_to_company'),
        'avg_company_actual_revenue':mean('company_actual_revenue'),'avg_market_volume':mean('market_volume'),
        'avg_company_cash_after_wages':mean('avg_company_cash_after_wages'),
        'avg_company_cash_after_resource':mean('avg_company_cash_after_resource'),
        'avg_unable_full_wages':mean('unable_full_wages'),'avg_stopped_cash':mean('stopped_cash'),'avg_stopped_stock':mean('stopped_stock'),
        'avg_food_zero_sum':mean('food_zero_sum'),'avg_money_zero_sum':mean('money_zero_sum'),
        'avg_birth_blocked_food_safety':mean('birth_blocked_food_safety'),
        'avg_birth_blocked_no_repro_goods':mean('birth_blocked_no_repro_goods'),
        'avg_birth_blocked_low_chance':mean('birth_blocked_low_chance'),
    },'results':res}

if __name__=='__main__':
    variants={
        'dev38_like_w50_m1000_no_resp': {'labor_reward_ratio':50,'company_initial_money':1000,'wage_resp':False,'bonus_per':0,'bonus_cap':0},
        'w55_m2000_resp': {'labor_reward_ratio':55,'company_initial_money':2000,'wage_resp':True,'bonus_per':10,'bonus_cap':20},
        'w60_m2000_resp': {'labor_reward_ratio':60,'company_initial_money':2000,'wage_resp':True,'bonus_per':10,'bonus_cap':20},
        'w60_m3000_resp': {'labor_reward_ratio':60,'company_initial_money':3000,'wage_resp':True,'bonus_per':10,'bonus_cap':20},
        'w65_m3000_resp': {'labor_reward_ratio':65,'company_initial_money':3000,'wage_resp':True,'bonus_per':10,'bonus_cap':20},
        'w60_m3000_no_resp': {'labor_reward_ratio':60,'company_initial_money':3000,'wage_resp':False,'bonus_per':0,'bonus_cap':0},
    }
    payload=[]
    for name,var in variants.items():
        payload.append(suite(name+'_5p_1000',1000,5,var))
        payload.append(suite(name+'_10p_1000',1000,10,var))
        print(payload[-2]['label'], payload[-2]['summary'])
        print(payload[-1]['label'], payload[-1]['summary'])
    with open('BOT8_dev39_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)

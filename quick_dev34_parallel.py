import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment
SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(max_turns, init_pop, labor_reward_ratio=None, inventory_dividend=False, dividend_ratio=10):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns; cfg['base']['initial_population']=init_pop; cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=bool(inventory_dividend); cfg['base']['inventory_sales_dividend_ratio']=dividend_ratio
    if labor_reward_ratio is not None:
        for p in cfg['population']: cfg['population'][p]['labor_reward_ratio']=labor_reward_ratio
    return cfg

def run_one(args):
    seed,max_turns,init_pop,labor_reward_ratio,inventory_dividend,dividend_ratio,collect=args
    random.seed(seed); cfg=make_cfg(max_turns,init_pop,labor_reward_ratio,inventory_dividend,dividend_ratio); env=Environment(cfg)
    init_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    death=Counter(); rows=[]; detail=[]
    for _ in range(max_turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn: death[ind.death_reason]+=1
        if env.current_summary_rows:
            r=env.current_summary_rows[0]; rows.append(r)
            if collect:
                detail.append({k:r.get(k) for k in ['Turn','PopCount','BirthCount','DeathCount','CriticalCount','FoodShortageCount','AvgBalance','TotalFood','TotalMedicalGoods','TotalReproductionGoods','FoodGini','MoneyGini','Bottom20FoodAvg','Bottom20MoneyAvg','FoodZeroCount','MoneyZeroCount','GovernmentFood','FoodBranchStock','FoodAidEligibleCount','FoodAidReceivedCount','FoodAidUnmetCount','Age0Count','Age1To3Count','Age1To3AvgFood','Age1To3AvgMoney','Age1To3CriticalCount','TotalWagesPaid','AvgWagePerWorker','WageToSurvivalCostRatio','CompanyCashAfterWages','CompanyUnableToPayFullWagesCount','InventorySalesDividendPaid']})
        if not ok: break
    final_pop=sum(len(pop) for pop in env.populations.values())
    final_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(c): return sum(float(r.get(c,0) or 0) for r in rows)
    def avgcol(c):
        xs=[float(r.get(c,0) or 0) for r in rows]
        return round(sum(xs)/len(xs),4) if xs else 0
    low=[r for r in rows if 0<int(r.get('PopCount',0) or 0)<5]
    def avg_low(c):
        xs=[float(r.get(c,0) or 0) for r in low]
        return round(sum(xs)/len(xs),4) if xs else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    last_birth=0
    for r in rows:
        if int(r.get('BirthCount',0) or 0)>0: last_birth=int(r.get('Turn',0) or 0)
    return {'seed':seed,'survived':env.turn>=max_turns and final_pop>0,'turns_run':env.turn,'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'last_birth_turn':last_birth,'death':dict(death),'money_delta':final_money-init_money,
        'avg_food_gini':avgcol('FoodGini'),'avg_money_gini':avgcol('MoneyGini'),'avg_bottom20_food':avgcol('Bottom20FoodAvg'),'avg_bottom20_money':avgcol('Bottom20MoneyAvg'),'food_zero_events':sumcol('FoodZeroCount'),'money_zero_events':sumcol('MoneyZeroCount'),'food_aid_unmet':sumcol('FoodAidUnmetCount'),'food_shortage_with_gov_food':sumcol('FoodShortageWithGovernmentFoodCount'),'medical_aid_unmet':sumcol('MedicalAidUnmetCount'),'critical_medical_aid_unmet':sumcol('CriticalMedicalAidUnmetCount'),'avg_wage':avgcol('AvgWagePerWorker'),'avg_wage_surv':avgcol('WageToSurvivalCostRatio'),'wages_paid':sumcol('TotalWagesPaid'),'unable_full_wage':sumcol('CompanyUnableToPayFullWagesCount'),'cash_stop':sumcol('CompanyProductionStoppedByCashCount'),'dividend_paid':sumcol('InventorySalesDividendPaid'),'low_bottom20_food':avg_low('Bottom20FoodAvg'),'low_bottom20_money':avg_low('Bottom20MoneyAvg'),'low_wage_surv':avg_low('WageToSurvivalCostRatio'),'detail':detail if collect else None}

def suite(label,max_turns,init_pop,labor_reward_ratio=None,inventory_dividend=False,dividend_ratio=10,seeds=SEEDS):
    args=[(s,max_turns,init_pop,labor_reward_ratio,inventory_dividend,dividend_ratio,False) for s in seeds]
    with mp.Pool(processes=min(len(args),8)) as pool: res=pool.map(run_one,args)
    agg=Counter(); ext=[]
    for r in res:
        agg.update(r['death']);
        if r['extinction_turn']: ext.append(r['extinction_turn'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {'label':label,'settings':{'max_turns':max_turns,'init_pop':init_pop,'labor_reward_ratio':labor_reward_ratio,'inventory_dividend':inventory_dividend,'dividend_ratio':dividend_ratio},'summary':{'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),'death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),'avg_food_gini':mean('avg_food_gini'),'avg_money_gini':mean('avg_money_gini'),'avg_bottom20_food':mean('avg_bottom20_food'),'avg_bottom20_money':mean('avg_bottom20_money'),'avg_food_zero_events':mean('food_zero_events'),'avg_food_aid_unmet':mean('food_aid_unmet'),'avg_food_shortage_with_gov_food':mean('food_shortage_with_gov_food'),'avg_medical_aid_unmet':mean('medical_aid_unmet'),'avg_critical_medical_aid_unmet':mean('critical_medical_aid_unmet'),'avg_wage':mean('avg_wage'),'avg_wage_surv':mean('avg_wage_surv'),'avg_wages_paid':mean('wages_paid'),'avg_unable_full_wage':mean('unable_full_wage'),'avg_cash_stop':mean('cash_stop'),'avg_dividend_paid':mean('dividend_paid'),'low_bottom20_food':mean('low_bottom20_food'),'low_bottom20_money':mean('low_bottom20_money'),'low_wage_surv':mean('low_wage_surv')},'results':res}

if __name__=='__main__':
    payload=[]
    payload.append({'label':'baseline_5p_10_detail_seed20260517','result':run_one((20260517,10,5,None,False,10,True))})
    experiments=[('baseline',None,False,10),('wage55',55,False,10),('wage60',60,False,10),('dividend5',None,True,5),('dividend10',None,True,10),('dividend15',None,True,15)]
    for name,w,div,ratio in experiments:
        payload.append(suite(f'{name}_5p_1000',1000,5,w,div,ratio))
    # 10p 只跑基线和表现最可能改变系统闭环的工资/分红组，避免长测时间过高。
    for name,w,div,ratio in experiments:
        payload.append(suite(f'{name}_10p_1000',1000,10,w,div,ratio))
    with open('BOT8_dev34_TEST_RESULTS.json','w',encoding='utf-8') as f: json.dump(payload,f,ensure_ascii=False,indent=2)
    for item in payload:
        if 'summary' in item: print(item['label'], item['summary'])
        else: print(item['label'], {'final_pop':item['result']['final_pop'],'births':item['result']['births'],'deaths':item['result']['deaths'],'details':item['result']['detail']})

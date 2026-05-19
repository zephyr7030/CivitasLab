import copy, random, json, statistics
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(max_turns=1000, init_pop=5, labor_reward_ratio=None, inventory_dividend=False, dividend_ratio=10):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=bool(inventory_dividend)
    cfg['base']['inventory_sales_dividend_ratio']=dividend_ratio
    for p in cfg['population']:
        if labor_reward_ratio is not None:
            cfg['population'][p]['labor_reward_ratio']=labor_reward_ratio
    return cfg

def run_one(seed,max_turns=1000,init_pop=5,labor_reward_ratio=None,inventory_dividend=False,dividend_ratio=10,collect_rows=False):
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop,labor_reward_ratio,inventory_dividend,dividend_ratio)
    env=Environment(cfg)
    init_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    death_reasons=Counter(); rows=[]; detail=[]
    for _ in range(max_turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn:
            death_reasons[ind.death_reason]+=1
        if env.current_summary_rows:
            row=dict(env.current_summary_rows[0]); rows.append(row)
            if collect_rows:
                detail.append({
                    'Turn':row.get('Turn'), 'PopCount':row.get('PopCount'), 'BirthCount':row.get('BirthCount'), 'DeathCount':row.get('DeathCount'),
                    'CriticalCount':row.get('CriticalCount'), 'FoodShortageCount':row.get('FoodShortageCount'),
                    'AvgBalance':row.get('AvgBalance'), 'AvgFood': round(row.get('TotalFood',0)/max(1,row.get('PopCount',0)),2) if row.get('PopCount',0) else 0,
                    'AvgMedicalGoods': round(row.get('TotalMedicalGoods',0)/max(1,row.get('PopCount',0)),2) if row.get('PopCount',0) else 0,
                    'AvgReproductionGoods': round(row.get('TotalReproductionGoods',0)/max(1,row.get('PopCount',0)),2) if row.get('PopCount',0) else 0,
                    'FoodGini':row.get('FoodGini'), 'MoneyGini':row.get('MoneyGini'), 'Bottom20FoodAvg':row.get('Bottom20FoodAvg'), 'Bottom20MoneyAvg':row.get('Bottom20MoneyAvg'),
                    'FoodZeroCount':row.get('FoodZeroCount'), 'MoneyZeroCount':row.get('MoneyZeroCount'),
                    'GovernmentFood':row.get('GovernmentFood'), 'CompanyFoodStock':row.get('FoodBranchStock'),
                    'FoodAidEligibleCount':row.get('FoodAidEligibleCount'), 'FoodAidReceivedCount':row.get('FoodAidReceivedCount'), 'FoodAidUnmetCount':row.get('FoodAidUnmetCount'),
                    'Age0Count':row.get('Age0Count'), 'Age1To3Count':row.get('Age1To3Count'), 'Age1To3AvgFood':row.get('Age1To3AvgFood'), 'Age1To3AvgMoney':row.get('Age1To3AvgMoney'), 'Age1To3CriticalCount':row.get('Age1To3CriticalCount'),
                    'TotalWagesPaid':row.get('TotalWagesPaid'), 'AvgWagePerWorker':row.get('AvgWagePerWorker'), 'WageToSurvivalCostRatio':row.get('WageToSurvivalCostRatio'),
                    'CompanyCashAfterWages':row.get('CompanyCashAfterWages'), 'CompanyUnableToPayFullWagesCount':row.get('CompanyUnableToPayFullWagesCount'),
                    'InventorySalesDividendPaid':row.get('InventorySalesDividendPaid'),
                })
        if not ok:
            break
    final_pop=sum(len(pop) for pop in env.populations.values())
    final_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(col): return sum(int(r.get(col,0) or 0) for r in rows)
    def avgcol(col):
        xs=[float(r.get(col,0) or 0) for r in rows]
        return round(sum(xs)/len(xs),4) if xs else 0
    def last(col): return rows[-1].get(col,0) if rows else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    low_pop_rows=[r for r in rows if 0 < int(r.get('PopCount',0) or 0) < 5]
    def avg_low(col):
        xs=[float(r.get(col,0) or 0) for r in low_pop_rows]
        return round(sum(xs)/len(xs),4) if xs else 0
    last_birth_turn=0
    for r in rows:
        if int(r.get('BirthCount',0) or 0)>0: last_birth_turn=int(r.get('Turn',0) or 0)
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,'last_birth_turn':last_birth_turn,
        'total_births':env.cumulative_birth_count.get('A',0),'total_deaths':env.cumulative_death_count.get('A',0),'death_reasons':dict(death_reasons),
        'money_delta':final_money-init_money,
        'avg_food_gini':avgcol('FoodGini'),'avg_money_gini':avgcol('MoneyGini'),'avg_bottom20_food':avgcol('Bottom20FoodAvg'),'avg_bottom20_money':avgcol('Bottom20MoneyAvg'),
        'sum_food_zero':sumcol('FoodZeroCount'),'sum_money_zero':sumcol('MoneyZeroCount'),
        'sum_food_aid_eligible':sumcol('FoodAidEligibleCount'),'sum_food_aid_received':sumcol('FoodAidReceivedCount'),'sum_food_aid_unmet':sumcol('FoodAidUnmetCount'),
        'sum_food_shortage_with_gov_food':sumcol('FoodShortageWithGovernmentFoodCount'),
        'sum_medical_aid_eligible':sumcol('MedicalAidEligibleCount'),'sum_medical_aid_received':sumcol('MedicalAidReceivedCount'),'sum_medical_aid_unmet':sumcol('MedicalAidUnmetCount'),
        'sum_critical_medical_need':sumcol('CriticalMedicalNeedCount'),'sum_critical_medical_aid_unmet':sumcol('CriticalMedicalAidUnmetCount'),
        'sum_age0_count':sumcol('Age0Count'),'sum_age1to3_critical':sumcol('Age1To3CriticalCount'),
        'avg_wage_per_worker':avgcol('AvgWagePerWorker'),'avg_wage_to_survival':avgcol('WageToSurvivalCostRatio'),'sum_wages_paid':sumcol('TotalWagesPaid'),
        'sum_unable_full_wage':sumcol('CompanyUnableToPayFullWagesCount'),'sum_cash_stop':sumcol('CompanyProductionStoppedByCashCount'),
        'sum_inventory_dividend_paid':sumcol('InventorySalesDividendPaid'),
        'lowpop_avg_bottom20_food':avg_low('Bottom20FoodAvg'),'lowpop_avg_bottom20_money':avg_low('Bottom20MoneyAvg'),'lowpop_avg_wage_to_survival':avg_low('WageToSurvivalCostRatio'),
        'final_company_money':sum(env.company_totals(p)['money'] for p in env.population_names),'final_government_money':sum(env.government_deposit.values()),'final_individual_money':sum(ind.balance for pop in env.populations.values() for ind in pop),
        'details':detail if collect_rows else None,
    }

def run_suite(label,max_turns,init_pop,labor_reward_ratio=None,inventory_dividend=False,dividend_ratio=10):
    results=[run_one(seed,max_turns,init_pop,labor_reward_ratio,inventory_dividend,dividend_ratio) for seed in SEEDS]
    agg=Counter(); ext=[]
    for r in results:
        agg.update(r['death_reasons'])
        if r['extinction_turn']: ext.append(r['extinction_turn'])
    def mean(k): return round(statistics.mean([r[k] for r in results]),4)
    return {'label':label,'settings':{'max_turns':max_turns,'init_pop':init_pop,'labor_reward_ratio':labor_reward_ratio,'inventory_dividend':inventory_dividend,'dividend_ratio':dividend_ratio},'summary':{
        'survival_count':sum(1 for r in results if r['survived']),'extinction_count':sum(1 for r in results if not r['survived']),'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
        'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('total_births'),'avg_deaths':mean('total_deaths'),'aggregate_death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in results),
        'avg_food_gini':mean('avg_food_gini'),'avg_money_gini':mean('avg_money_gini'),'avg_bottom20_food':mean('avg_bottom20_food'),'avg_bottom20_money':mean('avg_bottom20_money'),
        'avg_food_zero_events':mean('sum_food_zero'),'avg_money_zero_events':mean('sum_money_zero'),'avg_food_aid_unmet':mean('sum_food_aid_unmet'),'avg_food_shortage_with_gov_food':mean('sum_food_shortage_with_gov_food'),
        'avg_medical_aid_unmet':mean('sum_medical_aid_unmet'),'avg_critical_medical_aid_unmet':mean('sum_critical_medical_aid_unmet'),
        'avg_wage_per_worker':mean('avg_wage_per_worker'),'avg_wage_to_survival':mean('avg_wage_to_survival'),'avg_wages_paid':mean('sum_wages_paid'),
        'avg_unable_full_wage':mean('sum_unable_full_wage'),'avg_cash_stop':mean('sum_cash_stop'),'avg_inventory_dividend_paid':mean('sum_inventory_dividend_paid'),
        'lowpop_avg_bottom20_food':mean('lowpop_avg_bottom20_food'),'lowpop_avg_bottom20_money':mean('lowpop_avg_bottom20_money'),'lowpop_avg_wage_to_survival':mean('lowpop_avg_wage_to_survival'),
    },'results':results}

if __name__=='__main__':
    suites=[]
    suites.append({'label':'baseline_5p_10_detail_seed20260517','result':run_one(20260517,10,5,collect_rows=True)})
    for max_turns,init_pop in [(1000,5),(1000,10)]:
        suites.append(run_suite(f'baseline_{init_pop}p_{max_turns}',max_turns,init_pop))
        suites.append(run_suite(f'wage55_{init_pop}p_{max_turns}',max_turns,init_pop,labor_reward_ratio=55))
        suites.append(run_suite(f'wage60_{init_pop}p_{max_turns}',max_turns,init_pop,labor_reward_ratio=60))
        for ratio in [5,10,15]:
            suites.append(run_suite(f'inventory_dividend{ratio}_{init_pop}p_{max_turns}',max_turns,init_pop,inventory_dividend=True,dividend_ratio=ratio))
    with open('BOT8_dev34_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(suites,f,ensure_ascii=False,indent=2)
    for item in suites:
        if 'summary' in item:
            print(item['label'], item['summary'])
        else:
            r=item['result']
            print(item['label'], {'final_pop':r['final_pop'],'births':r['total_births'],'deaths':r['total_deaths'],'details':r['details']})

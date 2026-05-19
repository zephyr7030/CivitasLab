import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment
SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(max_turns=1000, init_pop=5, inventory_dividend=False, dividend_ratio=10,
             historical_only=True, cash_protection=True, min_cash_ratio=120, cash_floor_ratio=100):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=bool(inventory_dividend)
    cfg['base']['inventory_sales_dividend_ratio']=dividend_ratio
    cfg['base']['inventory_sales_dividend_historical_only']=bool(historical_only)
    cfg['base']['inventory_sales_dividend_cash_protection']=bool(cash_protection)
    cfg['base']['inventory_sales_dividend_min_cash_ratio']=min_cash_ratio
    cfg['base']['inventory_sales_dividend_cash_floor_ratio']=cash_floor_ratio
    return cfg

def run_one(args):
    seed,max_turns,init_pop,inventory_dividend,dividend_ratio,historical_only,cash_protection,min_cash_ratio,cash_floor_ratio,collect=args
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop,inventory_dividend,dividend_ratio,historical_only,cash_protection,min_cash_ratio,cash_floor_ratio)
    env=Environment(cfg)
    init_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    rows=[]; death=Counter(); details=[]
    for _ in range(max_turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn:
            death[ind.death_reason]+=1
        if env.current_summary_rows:
            r=dict(env.current_summary_rows[0]); rows.append(r)
            if collect:
                keys=['Turn','PopCount','BirthCount','DeathCount','CriticalCount','FoodShortageCount','AvgBalance','FoodGini','MoneyGini','Bottom20FoodAvg','Bottom20MoneyAvg','FoodZeroCount','MoneyZeroCount','TotalWagesPaid','AvgWagePerWorker','CompanyCashAfterWages','CompanyUnableToPayFullWagesCount','CompanyProductionStoppedByCashCount','HistoricalInventorySalesIncome','InventorySalesDividendPaid','InventorySalesDividendEligibleBranches','InventorySalesDividendBlockedByCashProtection','InventorySalesDividendBlockedByNoHistoricalIncome','InventorySalesDividendCashFloor']
                details.append({k:r.get(k) for k in keys})
        if not ok: break
    final_pop=sum(len(pop) for pop in env.populations.values())
    final_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(c): return sum(float(r.get(c,0) or 0) for r in rows)
    def avgcol(c):
        xs=[float(r.get(c,0) or 0) for r in rows]
        return round(sum(xs)/len(xs),4) if xs else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    low=[r for r in rows if 0<int(r.get('PopCount',0) or 0)<5]
    def avg_low(c):
        xs=[float(r.get(c,0) or 0) for r in low]
        return round(sum(xs)/len(xs),4) if xs else 0
    return {'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'death':dict(death),'money_delta':final_money-init_money,
            'avg_food_gini':avgcol('FoodGini'),'avg_money_gini':avgcol('MoneyGini'),'food_zero_events':sumcol('FoodZeroCount'),'money_zero_events':sumcol('MoneyZeroCount'),'avg_bottom20_food':avgcol('Bottom20FoodAvg'),'avg_bottom20_money':avgcol('Bottom20MoneyAvg'),
            'historical_income':sumcol('HistoricalInventorySalesIncome'),'dividend_paid':sumcol('InventorySalesDividendPaid'),'eligible_branches':sumcol('InventorySalesDividendEligibleBranches'),'blocked_cash':sumcol('InventorySalesDividendBlockedByCashProtection'),'blocked_no_hist':sumcol('InventorySalesDividendBlockedByNoHistoricalIncome'),'cash_floor_sum':sumcol('InventorySalesDividendCashFloor'),
            'unable_full_wage':sumcol('CompanyUnableToPayFullWagesCount'),'cash_stop':sumcol('CompanyProductionStoppedByCashCount'),'avg_wage':avgcol('AvgWagePerWorker'),'low_bottom20_money':avg_low('Bottom20MoneyAvg'),'low_bottom20_food':avg_low('Bottom20FoodAvg'),'details':details if collect else None}

def suite(label,max_turns,init_pop,inventory_dividend=False,dividend_ratio=10,historical_only=True,cash_protection=True,min_cash_ratio=120,cash_floor_ratio=100,seeds=SEEDS):
    args=[(s,max_turns,init_pop,inventory_dividend,dividend_ratio,historical_only,cash_protection,min_cash_ratio,cash_floor_ratio,False) for s in seeds]
    with mp.Pool(processes=min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    agg=Counter(); ext=[]
    for r in res:
        agg.update(r['death'])
        if r['extinction_turn']: ext.append(r['extinction_turn'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {'label':label,'settings':{'max_turns':max_turns,'init_pop':init_pop,'inventory_dividend':inventory_dividend,'dividend_ratio':dividend_ratio,'historical_only':historical_only,'cash_protection':cash_protection,'min_cash_ratio':min_cash_ratio,'cash_floor_ratio':cash_floor_ratio},'summary':{'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),'death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),'avg_food_gini':mean('avg_food_gini'),'avg_money_gini':mean('avg_money_gini'),'avg_bottom20_food':mean('avg_bottom20_food'),'avg_bottom20_money':mean('avg_bottom20_money'),'avg_food_zero_events':mean('food_zero_events'),'avg_money_zero_events':mean('money_zero_events'),'avg_historical_income':mean('historical_income'),'avg_dividend_paid':mean('dividend_paid'),'avg_eligible_branches':mean('eligible_branches'),'avg_blocked_cash':mean('blocked_cash'),'avg_blocked_no_hist':mean('blocked_no_hist'),'avg_unable_full_wage':mean('unable_full_wage'),'avg_cash_stop':mean('cash_stop'),'avg_wage':mean('avg_wage'),'low_bottom20_money':mean('low_bottom20_money'),'low_bottom20_food':mean('low_bottom20_food')},'results':res}

if __name__=='__main__':
    payload=[]
    payload.append({'label':'dev35_dividend15_5p_10_detail_seed20260517','result':run_one((20260517,10,5,True,15,True,True,120,100,True))})
    for init_pop in [5,10]:
        payload.append(suite(f'baseline_{init_pop}p_1000',1000,init_pop,False,10))
        for ratio in [12,13,14,15]:
            payload.append(suite(f'dev35_hist_cash_dividend{ratio}_{init_pop}p_1000',1000,init_pop,True,ratio,True,True,120,100))
    # 探究：同为15%，比较无现金保护/不限定历史收入，确认 dev35 保护是否必要。
    payload.append(suite('probe_unprotected_all_sales_dividend15_5p_1000',1000,5,True,15,False,False,120,100))
    payload.append(suite('probe_historical_only_no_cash_protection_dividend15_5p_1000',1000,5,True,15,True,False,120,100))
    with open('BOT8_dev35_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    for item in payload:
        if 'summary' in item:
            print(item['label'], item['summary'])
        else:
            print(item['label'], {'final_pop':item['result']['final_pop'],'details':item['result']['details']})

import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]


def make_cfg(max_turns=1000, init_pop=5, excess=False, ratio=20, min_cash=120, mode=1, recent_turns=5):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    # dev35 old inventory-sales dividend stays off unless a test explicitly changes it.
    cfg['base']['enable_inventory_sales_dividend']=False
    cfg['base']['enable_excess_cash_dividend']=bool(excess)
    cfg['base']['excess_cash_dividend_ratio']=ratio
    cfg['base']['excess_cash_dividend_min_cash_ratio']=min_cash
    cfg['base']['excess_cash_dividend_recipient_mode']=mode
    cfg['base']['excess_cash_dividend_recent_turns']=recent_turns
    return cfg


def run_one(args):
    seed,max_turns,init_pop,excess,ratio,min_cash,mode,recent_turns,collect=args
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop,excess,ratio,min_cash,mode,recent_turns)
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
                keys=['Turn','PopCount','BirthCount','DeathCount','CriticalCount','FoodShortageCount','AvgBalance','MoneyGini','FoodGini','Bottom20MoneyAvg','Bottom20FoodAvg','MoneyZeroCount','FoodZeroCount','TotalWagesPaid','WorkersCount','InventorySalesDividendPaid','ExcessCashDividendPaid','ExcessCashDividendRecipients','ExcessCashDividendPool','ExcessCashDividendEligibleBranches','ExcessCashDividendBlockedByNoExcessCash','ExcessCashDividendBlockedByNoRecipients','TurnsWithNoWorkersWhenPopBelow5','TurnsWithNoWagesWhenPopBelow5','CompanyHasCashButNoWorkersCount','CompanyHasStockButNoWorkersCount','Last3PopulationAvgLifeRemaining','Last3PopulationMinLifeRemaining','Last3PopulationReproductiveEligibleCount','DeathByLifeEndWithReproductionGoods','DeathByLifeEndWithFoodForBirth']
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
    last=rows[-1] if rows else {}
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,
        'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,
        'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'death':dict(death),
        'money_delta':final_money-init_money,
        'avg_money_gini':avgcol('MoneyGini'),'avg_food_gini':avgcol('FoodGini'),
        'money_zero_events':sumcol('MoneyZeroCount'),'food_zero_events':sumcol('FoodZeroCount'),
        'avg_bottom20_money':avgcol('Bottom20MoneyAvg'),'avg_bottom20_food':avgcol('Bottom20FoodAvg'),
        'excess_dividend_paid':sumcol('ExcessCashDividendPaid'),
        'excess_dividend_recipients':sumcol('ExcessCashDividendRecipients'),
        'excess_eligible_branches':sumcol('ExcessCashDividendEligibleBranches'),
        'blocked_no_excess_cash':sumcol('ExcessCashDividendBlockedByNoExcessCash'),
        'blocked_no_recipients':sumcol('ExcessCashDividendBlockedByNoRecipients'),
        'turns_no_workers_below5':int(last.get('TurnsWithNoWorkersWhenPopBelow5',0) or 0),
        'turns_no_wages_below5':int(last.get('TurnsWithNoWagesWhenPopBelow5',0) or 0),
        'cash_but_no_workers':int(last.get('CompanyHasCashButNoWorkersCount',0) or 0),
        'stock_but_no_workers':int(last.get('CompanyHasStockButNoWorkersCount',0) or 0),
        'death_life_with_repro_goods':int(last.get('DeathByLifeEndWithReproductionGoods',0) or 0),
        'death_life_with_food_for_birth':int(last.get('DeathByLifeEndWithFoodForBirth',0) or 0),
        'low_bottom20_money':avg_low('Bottom20MoneyAvg'),'low_bottom20_food':avg_low('Bottom20FoodAvg'),
        'details':details if collect else None,
    }


def suite(label,max_turns,init_pop,excess=False,ratio=20,min_cash=120,mode=1,recent_turns=5,seeds=SEEDS):
    args=[(s,max_turns,init_pop,excess,ratio,min_cash,mode,recent_turns,False) for s in seeds]
    with mp.Pool(processes=min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    agg=Counter(); ext=[]
    for r in res:
        agg.update(r['death'])
        if r['extinction_turn']:
            ext.append(r['extinction_turn'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {
        'label':label,
        'settings':{'max_turns':max_turns,'init_pop':init_pop,'excess':excess,'ratio':ratio,'min_cash':min_cash,'mode':mode,'recent_turns':recent_turns},
        'summary':{
            'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),
            'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
            'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),
            'death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),
            'avg_money_gini':mean('avg_money_gini'),'avg_food_gini':mean('avg_food_gini'),
            'avg_money_zero_events':mean('money_zero_events'),'avg_food_zero_events':mean('food_zero_events'),
            'avg_bottom20_money':mean('avg_bottom20_money'),'avg_bottom20_food':mean('avg_bottom20_food'),
            'avg_excess_dividend_paid':mean('excess_dividend_paid'),'avg_excess_recipients':mean('excess_dividend_recipients'),
            'avg_excess_eligible_branches':mean('excess_eligible_branches'),
            'avg_blocked_no_excess_cash':mean('blocked_no_excess_cash'),'avg_blocked_no_recipients':mean('blocked_no_recipients'),
            'avg_turns_no_workers_below5':mean('turns_no_workers_below5'),'avg_turns_no_wages_below5':mean('turns_no_wages_below5'),
            'avg_cash_but_no_workers':mean('cash_but_no_workers'),'avg_stock_but_no_workers':mean('stock_but_no_workers'),
            'avg_death_life_with_repro_goods':mean('death_life_with_repro_goods'),
            'avg_death_life_with_food_for_birth':mean('death_life_with_food_for_birth'),
            'low_bottom20_money':mean('low_bottom20_money'),'low_bottom20_food':mean('low_bottom20_food'),
        },
        'results':res,
    }


if __name__=='__main__':
    payload=[]
    payload.append({'label':'dev36_baseline_5p_10_detail_seed20260517','result':run_one((20260517,10,5,False,20,120,1,5,True))})
    for init_pop in [5,10]:
        payload.append(suite(f'baseline_{init_pop}p_1000',1000,init_pop,False))
    for ratio in [10,20,30]:
        payload.append(suite(f'excess_current_workers_ratio{ratio}_5p_1000',1000,5,True,ratio,120,1,5))
    for ratio in [10,20,30]:
        payload.append(suite(f'excess_current_workers_ratio{ratio}_10p_1000',1000,10,True,ratio,120,1,5))
    # 近期劳动者作为对照。mode=2 仍只分给近期同分公司劳动者，不是平均补贴。
    for ratio in [20,30]:
        payload.append(suite(f'excess_recent_workers_ratio{ratio}_5p_1000',1000,5,True,ratio,120,2,5))
    with open('BOT8_dev36_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    for item in payload:
        if 'summary' in item:
            print(item['label'], item['summary'])
        else:
            print(item['label'], {'final_pop':item['result']['final_pop'],'details':item['result']['details']})

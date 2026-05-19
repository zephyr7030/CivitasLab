import copy, random, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment
SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(turns,pop,mult=120,ratio=80,enabled=1):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=turns; cfg['base']['initial_population']=pop; cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=False; cfg['base']['enable_excess_cash_dividend']=False
    for pcfg in cfg['population'].values():
        pcfg['enable_company_hard_need_inventory_release']=enabled
        pcfg['company_hard_need_listing_multiplier']=mult
        pcfg['company_hard_need_min_listing_ratio']=ratio
    return cfg

def run_one(args):
    seed,turns,pop,mult,ratio=args
    random.seed(seed); env=Environment(make_cfg(turns,pop,mult,ratio))
    init_money=sum(ind.balance for pp in env.populations.values() for ind in pp)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    death=Counter(); rows=[]
    for _ in range(turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn: death[ind.death_reason]+=1
        if env.current_summary_rows: rows.append(dict(env.current_summary_rows[0]))
        if not ok: break
    final=sum(len(pp) for pp in env.populations.values())
    final_money=sum(ind.balance for pp in env.populations.values() for ind in pp)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    def sumcol(k): return sum(float(r.get(k,0) or 0) for r in rows)
    def avgcol(k): return sumcol(k)/len(rows) if rows else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    return dict(seed=seed,surv=env.turn>=turns and final>0,turn=env.turn,final=final,peak=max(pops) if pops else pop,birth=env.cumulative_birth_count.get('A',0),death=env.cumulative_death_count.get('A',0),reasons=dict(death),money_delta=final_money-init_money, foodSat=avgcol('FoodHardNeedSatisfiedRate'), reprSat=avgcol('ReproductionHardNeedSatisfiedRate'), noStock=sumcol('HardNeedBlockedByNoMarketStock'), noCash=sumcol('HardNeedBlockedByNoCash'), foodZero=sumcol('FoodZeroCount'))

def suite(turns,pop,mult,ratio,seeds=SEEDS):
    args=[(s,turns,pop,mult,ratio) for s in seeds]
    with mp.Pool(min(8,len(args))) as pool: res=pool.map(run_one,args)
    ext=[r['turn'] for r in res if not r['surv']]
    death=Counter(); [death.update(r['reasons']) for r in res]
    return dict(surv=sum(r['surv'] for r in res), avg_ext=round(statistics.mean(ext),1) if ext else None, avg_final=round(statistics.mean(r['final'] for r in res),1), avg_peak=round(statistics.mean(r['peak'] for r in res),1), avg_birth=round(statistics.mean(r['birth'] for r in res),1), avg_death=round(statistics.mean(r['death'] for r in res),1), death=dict(death), max_money=max(abs(r['money_delta']) for r in res), foodSat=round(statistics.mean(r['foodSat'] for r in res),3), reprSat=round(statistics.mean(r['reprSat'] for r in res),3), noStock=round(statistics.mean(r['noStock'] for r in res),1), noCash=round(statistics.mean(r['noCash'] for r in res),1), foodZero=round(statistics.mean(r['foodZero'] for r in res),1))

if __name__=='__main__':
    variants=[(80,120),(60,120),(50,120),(40,120),(30,120),(50,100),(40,100),(30,100),(60,80),(50,80),(40,80),(30,80),(20,80)]
    for ratio,mult in variants:
        print('\nVAR ratio',ratio,'mult',mult, flush=True)
        print('5p100',suite(100,5,mult,ratio), flush=True)
        print('10p100',suite(100,10,mult,ratio), flush=True)

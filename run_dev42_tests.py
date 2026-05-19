import copy, random, statistics, json, multiprocessing as mp
from collections import Counter
import config
from model import Environment
SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

def make_cfg(turns,pop,variant='default'):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=turns; cfg['base']['initial_population']=pop; cfg['base']['population_count']=1
    cfg['base']['enable_inventory_sales_dividend']=False; cfg['base']['enable_excess_cash_dividend']=False
    for pcfg in cfg['population'].values():
        # common current dev41/dev40 defaults
        pcfg['enable_company_hard_need_inventory_release']=1
        pcfg['company_hard_need_listing_multiplier']=100
        pcfg['company_hard_need_min_listing_ratio']=50
        if variant=='dev41_equivalent':
            pcfg['use_population_scaled_initials']=0
            pcfg['company_initial_money']=2000
            pcfg['company_initial_education_goods_ratio']=50
            pcfg['company_initial_reproduction_goods_ratio']=50
            pcfg['government_initial_money_per_capita']=0
            pcfg['government_initial_food_rounds']=0
            pcfg['government_initial_medical_goods_ratio']=0
            pcfg['government_initial_education_goods_ratio']=0
            pcfg['government_initial_reproduction_goods_ratio']=0
            pcfg['enable_repro_education_inventory_resilience']=0
        elif variant=='scaled_initials_only':
            pcfg['use_population_scaled_initials']=1
            pcfg['company_initial_money_per_capita']=400
            pcfg['government_initial_money_per_capita']=20
            pcfg['government_initial_food_rounds']=1
            pcfg['government_initial_medical_goods_ratio']=25
            pcfg['government_initial_education_goods_ratio']=25
            pcfg['government_initial_reproduction_goods_ratio']=25
            pcfg['company_initial_education_goods_ratio']=100
            pcfg['company_initial_reproduction_goods_ratio']=100
            pcfg['enable_repro_education_inventory_resilience']=0
        elif variant=='dev42_default':
            # use shipped defaults
            pass
        elif variant=='strong_resilience':
            pcfg['use_population_scaled_initials']=1
            pcfg['company_initial_money_per_capita']=400
            pcfg['government_initial_money_per_capita']=20
            pcfg['government_initial_food_rounds']=1
            pcfg['government_initial_medical_goods_ratio']=25
            pcfg['government_initial_education_goods_ratio']=25
            pcfg['government_initial_reproduction_goods_ratio']=25
            pcfg['company_initial_education_goods_ratio']=125
            pcfg['company_initial_reproduction_goods_ratio']=150
            pcfg['enable_repro_education_inventory_resilience']=1
            pcfg['repro_inventory_target_births_ratio']=200
            pcfg['education_inventory_target_births_ratio']=125
            pcfg['repro_education_inventory_resilience_weight']=75
    return cfg

def run_one(args):
    seed,turns,pop,variant=args
    random.seed(seed)
    env=Environment(make_cfg(turns,pop,variant))
    init_money=sum(ind.balance for pp in env.populations.values() for ind in pp)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    rows=[]; death=Counter()
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
    return dict(seed=seed,variant=variant,turns=env.turn,surv=env.turn>=turns and final>0,ext=None if final>0 else env.turn,final=final,peak=max(pops) if pops else pop,
        births=env.cumulative_birth_count.get('A',0),deaths=env.cumulative_death_count.get('A',0),reasons=dict(death),money_delta=final_money-init_money,
        no_repro=sumcol('BirthBlockedNoReproductionGoods'), no_food=sumcol('BirthBlockedNoFoodSafety'), low_chance=sumcol('BirthBlockedLowReproduceChance'),
        repro_sat=avgcol('ReproductionHardNeedSatisfiedRate'), food_sat=avgcol('FoodHardNeedSatisfiedRate'), no_stock=sumcol('HardNeedBlockedByNoMarketStock'), no_cash=sumcol('HardNeedBlockedByNoCash'),
        repro_res_gap=sumcol('ReproductionInventoryResilienceGap'), repro_res_weight=sumcol('ReproductionInventoryResilienceWeightAdded'), edu_res_gap=sumcol('EducationInventoryResilienceGap'), edu_res_weight=sumcol('EducationInventoryResilienceWeightAdded'),
        initial_company_money=rows[0].get('CompanyInitialMoneyEffective',0) if rows else 0, initial_repro_stock=rows[0].get('CompanyInitialReproductionStockTarget',0) if rows else 0,
        final_tail=rows[-10:])

def suite(turns,pop,variant):
    args=[(s,turns,pop,variant) for s in SEEDS]
    with mp.Pool(min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    ext=[r['ext'] for r in res if r['ext']]
    death=Counter(); [death.update(r['reasons']) for r in res]
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return dict(label=f'{variant}_{pop}p_{turns}', variant=variant, settings={'turns':turns,'pop':pop}, summary=dict(
        survival_count=sum(r['surv'] for r in res), extinction_count=sum(not r['surv'] for r in res), avg_extinction_turn=round(statistics.mean(ext),2) if ext else None,
        avg_final_pop=mean('final'), avg_peak_pop=mean('peak'), avg_births=mean('births'), avg_deaths=mean('deaths'), death_reasons=dict(death), max_abs_money_delta=max(abs(r['money_delta']) for r in res),
        avg_birth_blocked_no_repro=mean('no_repro'), avg_birth_blocked_no_food=mean('no_food'), avg_birth_blocked_low_chance=mean('low_chance'),
        avg_repro_hard_satisfied_rate=mean('repro_sat'), avg_food_hard_satisfied_rate=mean('food_sat'), avg_hard_blocked_no_stock=mean('no_stock'), avg_hard_blocked_no_cash=mean('no_cash'),
        avg_repro_resilience_gap=mean('repro_res_gap'), avg_repro_resilience_weight=mean('repro_res_weight'), avg_education_resilience_gap=mean('edu_res_gap'), avg_education_resilience_weight=mean('edu_res_weight'),
        avg_initial_company_money=mean('initial_company_money'), avg_initial_repro_stock=mean('initial_repro_stock')
        ), results=res)

if __name__=='__main__':
    variants=['dev41_equivalent','scaled_initials_only','dev42_default','strong_resilience']
    payload=[]
    for variant in variants:
        for turns,pop in [(1000,5),(1000,10)]:
            r=suite(turns,pop,variant)
            payload.append(r)
            print(r['label'], r['summary'], flush=True)
    with open('BOT8_dev42_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)

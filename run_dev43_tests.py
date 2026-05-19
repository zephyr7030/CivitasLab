import copy, random, statistics, json, multiprocessing as mp
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]
SHORT_SEEDS=[20260517,1,2,3,42]

def make_cfg(turns,pop):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=turns
    cfg['base']['initial_population']=pop
    cfg['base']['population_count']=1
    return cfg

def run_one(args):
    seed,turns,pop=args
    random.seed(seed)
    env=Environment(make_cfg(turns,pop))
    init_money=sum(ind.balance for pp in env.populations.values() for ind in pp)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    rows=[]; death=Counter()
    for _ in range(turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn:
            death[ind.death_reason]+=1
        if env.current_summary_rows:
            rows.append(dict(env.current_summary_rows[0]))
        if not ok:
            break
    final=sum(len(pp) for pp in env.populations.values())
    final_money=sum(ind.balance for pp in env.populations.values() for ind in pp)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    tail=rows[-min(200,len(rows)):] if rows else []
    def avg_tail(k): return round(sum(float(r.get(k,0) or 0) for r in tail)/len(tail),4) if tail else 0
    def sum_all(k): return round(sum(float(r.get(k,0) or 0) for r in rows),4) if rows else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    tail_pops=[int(r.get('PopCount',0) or 0) for r in tail]
    return dict(seed=seed, turns=env.turn, survived=(env.turn>=turns and final>0), extinction_turn=None if final>0 else env.turn,
        final_pop=final, peak_pop=max(pops) if pops else pop, avg_tail_pop=avg_tail('PopCount'), tail_min_pop=min(tail_pops) if tail_pops else 0, tail_max_pop=max(tail_pops) if tail_pops else 0,
        births=env.cumulative_birth_count.get('A',0), deaths=env.cumulative_death_count.get('A',0), death_reasons=dict(death), money_delta=round(final_money-init_money,6),
        avg_resource_pressure=avg_tail('ResourcePressure'), avg_env_health=avg_tail('EnvHealth'), avg_env_resource_use_rate=avg_tail('EnvResourceUseRate'),
        avg_resource_use_to_regen=avg_tail('ResourceUseToRegenRatio'), avg_labor_resource_unused=avg_tail('LaborResourceUnused'), avg_labor_resource_unused_rate=avg_tail('LaborResourceUnusedRate'),
        avg_resource_limit_reached=avg_tail('ResourceLimitReached'), avg_resource_claim=avg_tail('PopulationResourceClaim'), avg_resource_quota=avg_tail('PopulationResourceQuota'), avg_resource_used=avg_tail('PopulationResourceUsed'), avg_resource_shortage=avg_tail('PopulationResourceShortage'),
        avg_food_target=avg_tail('FoodOperatingStockTarget'), avg_repro_target=avg_tail('ReproductionOperatingStockTarget'), avg_edu_target=avg_tail('EducationOperatingStockTarget'),
        avg_food_company_stock=avg_tail('FoodBranchStock'), avg_repro_company_stock=avg_tail('ReproductionBranchStock'), avg_edu_company_stock=avg_tail('EducationBranchStock'),
        avg_food_hard_sat=avg_tail('FoodHardNeedSatisfiedRate'), avg_repro_hard_sat=avg_tail('ReproductionHardNeedSatisfiedRate'),
        sum_birth_block_no_repro=sum_all('BirthBlockedNoReproductionGoods'), sum_birth_block_no_food=sum_all('BirthBlockedNoFoodSafety'), sum_no_stock=sum_all('HardNeedBlockedByNoMarketStock'))

def suite(turns,pop,seeds):
    args=[(s,turns,pop) for s in seeds]
    with mp.Pool(min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    ext=[r['extinction_turn'] for r in res if r['extinction_turn']]
    deaths=Counter(); [deaths.update(r['death_reasons']) for r in res]
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return dict(label=f'dev43_diagnostic_{pop}p_{turns}_{len(seeds)}seeds', settings={'turns':turns,'pop':pop,'seeds':seeds}, summary=dict(
        survival_count=sum(r['survived'] for r in res), extinction_count=sum(not r['survived'] for r in res), avg_extinction_turn=round(statistics.mean(ext),2) if ext else None,
        avg_final_pop=mean('final_pop'), avg_peak_pop=mean('peak_pop'), avg_tail_pop=mean('avg_tail_pop'), avg_tail_min_pop=mean('tail_min_pop'), avg_tail_max_pop=mean('tail_max_pop'),
        avg_births=mean('births'), avg_deaths=mean('deaths'), death_reasons=dict(deaths), max_abs_money_delta=max(abs(r['money_delta']) for r in res),
        avg_resource_pressure=mean('avg_resource_pressure'), avg_env_health=mean('avg_env_health'), avg_env_resource_use_rate=mean('avg_env_resource_use_rate'), avg_resource_use_to_regen=mean('avg_resource_use_to_regen'),
        avg_labor_resource_unused=mean('avg_labor_resource_unused'), avg_labor_resource_unused_rate=mean('avg_labor_resource_unused_rate'), avg_resource_limit_reached=mean('avg_resource_limit_reached'),
        avg_resource_claim=mean('avg_resource_claim'), avg_resource_quota=mean('avg_resource_quota'), avg_resource_used=mean('avg_resource_used'), avg_resource_shortage=mean('avg_resource_shortage'),
        avg_food_target=mean('avg_food_target'), avg_repro_target=mean('avg_repro_target'), avg_edu_target=mean('avg_edu_target'),
        avg_food_company_stock=mean('avg_food_company_stock'), avg_repro_company_stock=mean('avg_repro_company_stock'), avg_edu_company_stock=mean('avg_edu_company_stock'),
        avg_food_hard_satisfied=mean('avg_food_hard_sat'), avg_repro_hard_satisfied=mean('avg_repro_hard_sat'), avg_birth_blocked_no_repro=mean('sum_birth_block_no_repro'), avg_birth_blocked_no_food=mean('sum_birth_block_no_food'), avg_hard_need_blocked_no_stock=mean('sum_no_stock')
    ), results=res)

if __name__=='__main__':
    payload=[]
    for turns,pop,seeds in [(1000,5,SEEDS),(1000,10,SHORT_SEEDS)]:
        r=suite(turns,pop,seeds)
        payload.append(r)
        print(r['label'], json.dumps(r['summary'],ensure_ascii=False), flush=True)
    with open('BOT8_dev43_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)

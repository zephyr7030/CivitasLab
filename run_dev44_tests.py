import copy, random, statistics, json, multiprocessing as mp
from collections import Counter
import config
from model import Environment
from output import validate_summary_headers, SUMMARY_HEADERS

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]
SHORT_SEEDS=[20260517,1,2,3,42]
TWENTY_SEEDS=[20260517,1,2]


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
    header_missing=[]
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
    check=validate_summary_headers(env.summary_output_rows, SUMMARY_HEADERS)
    header_missing=check['missing_headers']
    tail=rows[-min(200,len(rows)):] if rows else []
    def avg_tail(k): return round(sum(float(r.get(k,0) or 0) for r in tail)/len(tail),4) if tail else 0
    def sum_all(k): return round(sum(float(r.get(k,0) or 0) for r in rows),4) if rows else 0
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    tail_pops=[int(r.get('PopCount',0) or 0) for r in tail]
    return dict(seed=seed, turns=env.turn, survived=(env.turn>=turns and final>0), extinction_turn=None if final>0 else env.turn,
        final_pop=final, peak_pop=max(pops) if pops else pop, avg_tail_pop=avg_tail('PopCount'), tail_min_pop=min(tail_pops) if tail_pops else 0, tail_max_pop=max(tail_pops) if tail_pops else 0,
        births=env.cumulative_birth_count.get('A',0), deaths=env.cumulative_death_count.get('A',0), death_reasons=dict(death), money_delta=round(final_money-init_money,6), header_missing=header_missing,
        avg_resource_use_to_regen=avg_tail('ResourceUseToRegenRatio'), avg_labor_resource_unused_rate=avg_tail('LaborResourceUnusedRate'), avg_resource_limit_reached=avg_tail('ResourceLimitReached'),
        avg_food_hard_satisfied=avg_tail('FoodHardNeedSatisfiedRate'), avg_medical_hard_satisfied=avg_tail('MedicalHardNeedSatisfiedRate'), avg_repro_hard_satisfied=avg_tail('ReproductionHardNeedSatisfiedRate'),
        avg_food_prod_bonus=avg_tail('FoodHardNeedProductionBonus'), avg_medical_prod_bonus=avg_tail('MedicalHardNeedProductionBonus'), avg_repro_prod_bonus=avg_tail('ReproductionHardNeedProductionBonus'), avg_edu_prod_bonus=avg_tail('EducationNeedProductionBonus'),
        sum_food_unmet_prod=sum_all('FoodHardNeedUnmetForProduction'), sum_medical_unmet_prod=sum_all('MedicalHardNeedUnmetForProduction'), sum_repro_unmet_prod=sum_all('ReproductionHardNeedUnmetForProduction'),
        sum_food_produced=sum_all('FoodProducedTotal'), sum_medical_produced=sum_all('MedicalGoodsProducedTotal'), sum_repro_produced=sum_all('ReproductionGoodsProducedTotal'), sum_edu_produced=sum_all('EducationGoodsProducedTotal'),
        sum_no_stock=sum_all('HardNeedBlockedByNoMarketStock'), sum_food_unsat=sum_all('FoodHardUnsatisfiedAmount'), sum_medical_unsat=sum_all('MedicalHardUnsatisfiedAmount'), sum_repro_unsat=sum_all('ReproductionHardUnsatisfiedAmount'))


def suite(turns,pop,seeds):
    args=[(s,turns,pop) for s in seeds]
    with mp.Pool(min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    ext=[r['extinction_turn'] for r in res if r['extinction_turn']]
    deaths=Counter(); [deaths.update(r['death_reasons']) for r in res]
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return dict(label=f'dev44_{pop}p_{turns}_{len(seeds)}seeds', settings={'turns':turns,'pop':pop,'seeds':seeds}, summary=dict(
        survival_count=sum(r['survived'] for r in res), extinction_count=sum(not r['survived'] for r in res), avg_extinction_turn=round(statistics.mean(ext),2) if ext else None,
        avg_final_pop=mean('final_pop'), avg_peak_pop=mean('peak_pop'), avg_tail_pop=mean('avg_tail_pop'), avg_tail_min_pop=mean('tail_min_pop'), avg_tail_max_pop=mean('tail_max_pop'),
        avg_births=mean('births'), avg_deaths=mean('deaths'), death_reasons=dict(deaths), max_abs_money_delta=max(abs(r['money_delta']) for r in res), any_header_missing=any(r['header_missing'] for r in res),
        avg_resource_use_to_regen=mean('avg_resource_use_to_regen'), avg_labor_resource_unused_rate=mean('avg_labor_resource_unused_rate'), avg_resource_limit_reached=mean('avg_resource_limit_reached'),
        avg_food_hard_satisfied=mean('avg_food_hard_satisfied'), avg_medical_hard_satisfied=mean('avg_medical_hard_satisfied'), avg_repro_hard_satisfied=mean('avg_repro_hard_satisfied'),
        avg_food_prod_bonus=mean('avg_food_prod_bonus'), avg_medical_prod_bonus=mean('avg_medical_prod_bonus'), avg_repro_prod_bonus=mean('avg_repro_prod_bonus'), avg_edu_prod_bonus=mean('avg_edu_prod_bonus'),
        avg_hard_need_blocked_no_stock=mean('sum_no_stock'), avg_food_unsatisfied=mean('sum_food_unsat'), avg_medical_unsatisfied=mean('sum_medical_unsat'), avg_repro_unsatisfied=mean('sum_repro_unsat'),
        avg_food_produced=mean('sum_food_produced'), avg_medical_produced=mean('sum_medical_produced'), avg_repro_produced=mean('sum_repro_produced'), avg_edu_produced=mean('sum_edu_produced')
    ), results=res)

if __name__=='__main__':
    payload=[]
    for turns,pop,seeds in [(1000,5,SEEDS),(1000,10,SHORT_SEEDS),(1000,20,TWENTY_SEEDS)]:
        r=suite(turns,pop,seeds)
        payload.append(r)
        print(r['label'], json.dumps(r['summary'],ensure_ascii=False), flush=True)
    with open('BOT8_dev44_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)

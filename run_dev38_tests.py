import copy, random, json, statistics, multiprocessing as mp
from collections import Counter
import config
from model import Environment

SEEDS=[20260517,1,2,3,42,100,999,2026,17,88]

DETAIL_KEYS=[
    'Turn','PopCount','BirthCount','DeathCount','CriticalCount','FoodShortageCount','MedicalShortageCount',
    'AvgBalance','AvgFood' if False else 'TotalFood','MoneyGini','FoodGini','MoneyZeroCount','FoodZeroCount',
    'LaborCandidateCount','LaborWorkerCount','TotalWagesPaid','WorkersCount','TurnsWithNoWorkersWhenPopBelow5','TurnsWithNoWagesWhenPopBelow5',
    'PopBelow5TurnCount','PopBelow3TurnCount','LaborEligibleCountWhenPopBelow5','LaborEligibleCountWhenPopBelow3',
    'LaborWillingCountWhenPopBelow5','LaborWillingCountWhenPopBelow3','ActualWorkerCountWhenPopBelow5','ActualWorkerCountWhenPopBelow3',
    'NoWorkerReasonSickCount','NoWorkerReasonCriticalCount','NoWorkerReasonLowLaborCount','NoWorkerReasonNoCompanyDemandCount',
    'NoWorkerReasonNoExpectedProfitCount','NoWorkerReasonNoResourceCount','CompanyDemandForWorkersWhenPopBelow5','CompanyDemandForWorkersWhenPopBelow3',
    'BranchesWithPositiveExpectedProfitWhenPopBelow5','BranchesWithPositiveExpectedProfitWhenPopBelow3','BranchesStoppedByStockWhenPopBelow5',
    'BranchesStoppedByCashWhenPopBelow5','BranchesStoppedByResourceWhenPopBelow5','GovernmentProductionResourceWhenPopBelow5',
    'CompanyTotalStockWhenPopBelow5','CompanyTotalMoneyWhenPopBelow5','LowPopSnapshotCount','LastIndividualsAvgMoney','LastIndividualsAvgFood',
    'LastIndividualsAvgMedicalGoods','LastIndividualsAvgReproductionGoods','LastIndividualsAvgLabor','LastIndividualsAvgReproduce',
    'LastIndividualsAvgLifeRemaining','LastIndividualsAvgAge','LastIndividualsSickCount','LastIndividualsCriticalCount',
    'LastIndividualsCanWorkCount','LastIndividualsCanReproduceCount','LastIndividualsHasFoodForBirthCount','LastIndividualsHasReproductionGoodsCount',
    'LifeEndWithCanReproduce','LifeEndWithCanWork','LifeEndWithFoodAndReproductionGoods','LastDeathLifeRemaining','LastDeathHadFoodForBirth',
    'LastDeathHadReproductionGoods','LastDeathWasSick','LastDeathWasCritical','LastDeathCouldWork','LastDeathCouldReproduce',
    'Last3PopulationAvgLifeRemaining','Last3PopulationMinLifeRemaining','Last3PopulationReproductiveEligibleCount',
    'BirthBlockedNoReproductionGoods','BirthBlockedNoFoodSafety','BirthBlockedLowReproduceChance','SecondaryBirthSuccessCount',
    'LaborCandidateRawCount','LaborCandidatesTrimmedByTendency','LaborAllocatedCandidateCount','LaborCandidatesWithoutAllocation',
    'LaborPositiveProfitButNoWorkerWhenPopBelow5','ParentFoodRequirement','PotentialParentCountWhenPopBelow5',
    'PotentialParentWithReproductionGoodsWhenPopBelow5','PotentialParentFoodReadyWhenPopBelow5','ParentFoodGapWhenPopBelow5',
    'ParentFoodGapWhenPopBelow3','LastIndividualsParentFoodGapAvg','FoodBoughtByPotentialParent','FoodAidToPotentialParent',
    'BirthBlockedFoodSafetyWithReproductionGoods'
]


def make_cfg(max_turns=1000, init_pop=5):
    cfg=copy.deepcopy(config.DEFAULT_SETTINGS)
    cfg['base']['max_turns']=max_turns
    cfg['base']['initial_population']=init_pop
    cfg['base']['population_count']=1
    # dev38 is diagnostic-only: keep experimental dividends off by default.
    cfg['base']['enable_inventory_sales_dividend']=False
    cfg['base']['enable_excess_cash_dividend']=False
    return cfg


def run_one(args):
    seed,max_turns,init_pop,collect=args
    random.seed(seed)
    cfg=make_cfg(max_turns,init_pop)
    env=Environment(cfg)
    init_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    rows=[]; death=Counter(); details=[]
    final_tail=[]
    for _ in range(max_turns):
        ok=env.run_turn()
        for p,ind in env.dead_individuals_this_turn:
            death[ind.death_reason]+=1
        if env.current_summary_rows:
            r=dict(env.current_summary_rows[0]); rows.append(r)
            if collect or int(r.get('PopCount',0) or 0) <= 5 or (not ok):
                details.append({k:r.get(k) for k in DETAIL_KEYS})
                details=details[-80:]
        if not ok:
            break
    final_pop=sum(len(pop) for pop in env.populations.values())
    final_money=sum(ind.balance for pop in env.populations.values() for ind in pop)+sum(env.government_deposit.values())+sum(env.company_totals(p)['money'] for p in env.population_names)
    pops=[int(r.get('PopCount',0) or 0) for r in rows]
    low=[r for r in rows if 0<int(r.get('PopCount',0) or 0)<5]
    below3=[r for r in rows if 0<int(r.get('PopCount',0) or 0)<3]
    def sumcol(c, subset=None):
        ss=subset if subset is not None else rows
        return sum(float(r.get(c,0) or 0) for r in ss)
    def avgcol(c, subset=None):
        ss=subset if subset is not None else rows
        xs=[float(r.get(c,0) or 0) for r in ss]
        return round(sum(xs)/len(xs),4) if xs else 0
    def maxcol(c, subset=None):
        ss=subset if subset is not None else rows
        xs=[float(r.get(c,0) or 0) for r in ss]
        return max(xs) if xs else 0
    last=rows[-1] if rows else {}
    return {
        'seed':seed,'turns_run':env.turn,'survived':env.turn>=max_turns and final_pop>0,
        'extinction_turn':None if final_pop>0 else env.turn,'final_pop':final_pop,
        'peak_pop':max(pops) if pops else init_pop,'avg_pop':round(sum(pops)/len(pops),2) if pops else 0,
        'births':env.cumulative_birth_count.get('A',0),'deaths':env.cumulative_death_count.get('A',0),'death_reasons':dict(death),
        'money_delta':final_money-init_money,
        'low_turns':len(low),'below3_turns':len(below3),
        'turns_no_workers_below5':int(last.get('TurnsWithNoWorkersWhenPopBelow5',0) or 0),
        'turns_no_wages_below5':int(last.get('TurnsWithNoWagesWhenPopBelow5',0) or 0),
        'cash_but_no_workers':int(last.get('CompanyHasCashButNoWorkersCount',0) or 0),
        'stock_but_no_workers':int(last.get('CompanyHasStockButNoWorkersCount',0) or 0),
        'avg_low_labor_eligible':avgcol('LaborEligibleCountWhenPopBelow5',low),
        'avg_low_labor_willing':avgcol('LaborWillingCountWhenPopBelow5',low),
        'avg_low_actual_workers':avgcol('ActualWorkerCountWhenPopBelow5',low),
        'avg_labor_raw_candidates':avgcol('LaborCandidateRawCount',low),
        'avg_labor_trimmed_by_tendency':avgcol('LaborCandidatesTrimmedByTendency',low),
        'avg_labor_allocated_candidates':avgcol('LaborAllocatedCandidateCount',low),
        'avg_labor_without_allocation':avgcol('LaborCandidatesWithoutAllocation',low),
        'sum_positive_profit_but_no_worker_low':sumcol('LaborPositiveProfitButNoWorkerWhenPopBelow5',low),
        'sum_low_no_worker_low_labor':sumcol('NoWorkerReasonLowLaborCount',low),
        'sum_low_no_worker_expected_profit':sumcol('NoWorkerReasonNoExpectedProfitCount',low),
        'sum_low_no_worker_resource':sumcol('NoWorkerReasonNoResourceCount',low),
        'sum_low_critical_count':sumcol('NoWorkerReasonCriticalCount',low),
        'sum_low_sick_count':sumcol('NoWorkerReasonSickCount',low),
        'avg_low_positive_profit_branches':avgcol('BranchesWithPositiveExpectedProfitWhenPopBelow5',low),
        'avg_low_company_stock':avgcol('CompanyTotalStockWhenPopBelow5',low),
        'avg_low_company_money':avgcol('CompanyTotalMoneyWhenPopBelow5',low),
        'avg_last_ind_can_work':avgcol('LastIndividualsCanWorkCount',below3),
        'avg_last_ind_can_reproduce':avgcol('LastIndividualsCanReproduceCount',below3),
        'avg_last_ind_has_food_birth':avgcol('LastIndividualsHasFoodForBirthCount',below3),
        'avg_last_ind_has_rep_goods':avgcol('LastIndividualsHasReproductionGoodsCount',below3),
        'avg_last_life_remaining':avgcol('LastIndividualsAvgLifeRemaining',below3),
        'avg_parent_food_gap_below5':avgcol('ParentFoodGapWhenPopBelow5',low),
        'avg_parent_food_gap_below3':avgcol('ParentFoodGapWhenPopBelow3',below3),
        'avg_last_parent_food_gap':avgcol('LastIndividualsParentFoodGapAvg',below3),
        'sum_food_bought_by_potential_parent':sumcol('FoodBoughtByPotentialParent'),
        'sum_food_aid_to_potential_parent':sumcol('FoodAidToPotentialParent'),
        'sum_birth_blocked_food_safety_with_goods':sumcol('BirthBlockedFoodSafetyWithReproductionGoods'),
        'avg_potential_parent_count_low':avgcol('PotentialParentCountWhenPopBelow5',low),
        'avg_potential_parent_with_goods_low':avgcol('PotentialParentWithReproductionGoodsWhenPopBelow5',low),
        'avg_potential_parent_food_ready_low':avgcol('PotentialParentFoodReadyWhenPopBelow5',low),
        'life_end_with_can_work':sumcol('LifeEndWithCanWork'),
        'life_end_with_can_reproduce':sumcol('LifeEndWithCanReproduce'),
        'life_end_with_food_and_repro_goods':sumcol('LifeEndWithFoodAndReproductionGoods'),
        'last_death':{k:last.get(k) for k in ['LastDeathLifeRemaining','LastDeathHadFoodForBirth','LastDeathHadReproductionGoods','LastDeathWasSick','LastDeathWasCritical','LastDeathCouldWork','LastDeathCouldReproduce','LastSurvivorDeathReason']},
        'final_details':details,
    }


def suite(label,max_turns,init_pop,seeds=SEEDS):
    args=[(s,max_turns,init_pop,False) for s in seeds]
    with mp.Pool(processes=min(8,len(args))) as pool:
        res=pool.map(run_one,args)
    agg=Counter(); ext=[]
    for r in res:
        agg.update(r['death_reasons'])
        if r['extinction_turn']:
            ext.append(r['extinction_turn'])
    def mean(k): return round(statistics.mean([r[k] for r in res]),4)
    return {
        'label':label,
        'settings':{'max_turns':max_turns,'init_pop':init_pop},
        'summary':{
            'survival_count':sum(r['survived'] for r in res),'extinction_count':sum(not r['survived'] for r in res),
            'avg_extinction_turn':round(statistics.mean(ext),2) if ext else None,
            'avg_final_pop':mean('final_pop'),'avg_peak_pop':mean('peak_pop'),'avg_births':mean('births'),'avg_deaths':mean('deaths'),
            'death_reasons':dict(agg),'max_abs_money_delta':max(abs(r['money_delta']) for r in res),
            'avg_low_turns':mean('low_turns'),'avg_below3_turns':mean('below3_turns'),
            'avg_turns_no_workers_below5':mean('turns_no_workers_below5'),'avg_turns_no_wages_below5':mean('turns_no_wages_below5'),
            'avg_cash_but_no_workers':mean('cash_but_no_workers'),'avg_stock_but_no_workers':mean('stock_but_no_workers'),
            'avg_low_labor_eligible':mean('avg_low_labor_eligible'),'avg_low_labor_willing':mean('avg_low_labor_willing'),
            'avg_low_actual_workers':mean('avg_low_actual_workers'),
            'avg_labor_raw_candidates':mean('avg_labor_raw_candidates'),
            'avg_labor_trimmed_by_tendency':mean('avg_labor_trimmed_by_tendency'),
            'avg_labor_allocated_candidates':mean('avg_labor_allocated_candidates'),
            'avg_labor_without_allocation':mean('avg_labor_without_allocation'),
            'avg_positive_profit_but_no_worker_low':mean('sum_positive_profit_but_no_worker_low'),
            'avg_low_no_worker_low_labor':mean('sum_low_no_worker_low_labor'),
            'avg_low_no_worker_expected_profit':mean('sum_low_no_worker_expected_profit'),
            'avg_low_no_worker_resource':mean('sum_low_no_worker_resource'),
            'avg_low_sick_count':mean('sum_low_sick_count'),'avg_low_critical_count':mean('sum_low_critical_count'),
            'avg_low_positive_profit_branches':mean('avg_low_positive_profit_branches'),
            'avg_low_company_stock':mean('avg_low_company_stock'),'avg_low_company_money':mean('avg_low_company_money'),
            'avg_last_ind_can_work':mean('avg_last_ind_can_work'),'avg_last_ind_can_reproduce':mean('avg_last_ind_can_reproduce'),
            'avg_last_ind_has_food_birth':mean('avg_last_ind_has_food_birth'),'avg_last_ind_has_rep_goods':mean('avg_last_ind_has_rep_goods'),
            'avg_last_life_remaining':mean('avg_last_life_remaining'),
            'avg_parent_food_gap_below5':mean('avg_parent_food_gap_below5'),
            'avg_parent_food_gap_below3':mean('avg_parent_food_gap_below3'),
            'avg_last_parent_food_gap':mean('avg_last_parent_food_gap'),
            'avg_food_bought_by_potential_parent':mean('sum_food_bought_by_potential_parent'),
            'avg_food_aid_to_potential_parent':mean('sum_food_aid_to_potential_parent'),
            'avg_birth_blocked_food_safety_with_goods':mean('sum_birth_blocked_food_safety_with_goods'),
            'avg_potential_parent_count_low':mean('avg_potential_parent_count_low'),
            'avg_potential_parent_with_goods_low':mean('avg_potential_parent_with_goods_low'),
            'avg_potential_parent_food_ready_low':mean('avg_potential_parent_food_ready_low'),
            'avg_life_end_with_can_work':mean('life_end_with_can_work'),
            'avg_life_end_with_can_reproduce':mean('life_end_with_can_reproduce'),
            'avg_life_end_with_food_and_repro_goods':mean('life_end_with_food_and_repro_goods'),
        },
        'results':res,
    }

if __name__=='__main__':
    payload=[]
    payload.append({'label':'dev38_5p_10_detail_seed20260517','result':run_one((20260517,10,5,True))})
    payload.append(suite('dev38_baseline_5p_1000',1000,5))
    payload.append(suite('dev38_baseline_10p_1000',1000,10))
    # Collect full low-pop tail details for known/representative seeds.
    for seed, init_pop in [(20260517,5),(1,5),(42,5),(88,10)]:
        payload.append({'label':f'dev38_tail_detail_seed{seed}_{init_pop}p_1000','result':run_one((seed,1000,init_pop,True))})
    with open('BOT8_dev38_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    for item in payload:
        if 'summary' in item:
            print(item['label'], item['summary'])
        else:
            r=item['result']
            print(item['label'], {'turns_run':r['turns_run'],'final_pop':r['final_pop'],'extinction_turn':r['extinction_turn'],'births':r['births'],'deaths':r['deaths'],'low_turns':r['low_turns'],'turns_no_workers_below5':r['turns_no_workers_below5'],'last_death':r['last_death']})

import json
from run_dev36_tests import suite, run_one
payload=[]
configs=[
    ('baseline_5p_1000',1000,5,False,20,120,1,5),
    ('baseline_10p_1000',1000,10,False,20,120,1,5),
    ('excess_current_workers_ratio10_5p_1000',1000,5,True,10,120,1,5),
    ('excess_current_workers_ratio20_5p_1000',1000,5,True,20,120,1,5),
    ('excess_current_workers_ratio30_5p_1000',1000,5,True,30,120,1,5),
    ('excess_current_workers_ratio10_10p_1000',1000,10,True,10,120,1,5),
    ('excess_current_workers_ratio20_10p_1000',1000,10,True,20,120,1,5),
    ('excess_current_workers_ratio30_10p_1000',1000,10,True,30,120,1,5),
    ('excess_recent_workers_ratio20_5p_1000',1000,5,True,20,120,2,5),
    ('excess_recent_workers_ratio30_5p_1000',1000,5,True,30,120,2,5),
]
payload.append({'label':'dev36_baseline_5p_10_detail_seed20260517','result':run_one((20260517,10,5,False,20,120,1,5,True))})
for cfg in configs:
    print('run',cfg[0],flush=True)
    item=suite(*cfg)
    payload.append(item)
    with open('BOT8_dev36_TEST_RESULTS.json','w',encoding='utf-8') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
    print(cfg[0], item['summary'], flush=True)

# BOT8 dev38 实装报告

## 目标

继续核查 dev37 发现的两个断点：

1. 低人口时候选劳动者为何没有稳定转化为实际劳动者；
2. 最后 1–3 人为何长期达不到父代出生食物安全线。

本版只新增诊断，不改变模型行为。

## 未做事项

- 未调高工资；
- 未提高生育率；
- 未延长寿命；
- 未默认开启任何分红；
- 未加入人口恢复倍率、最低出生率、强制出生、自给补给或政府凭空创造资源。

## 修改文件

- `config.py`：版本号 37 → 38；
- `model.py`：新增 dev38 诊断字段和记录逻辑；
- `output.py`：新增 summary 输出列；
- `README.md`：追加 dev38 说明；
- `run_dev38_tests.py`：新增测试脚本。

## 新增诊断字段

```text
LaborCandidateRawCount
LaborCandidatesTrimmedByTendency
LaborAllocatedCandidateCount
LaborCandidatesWithoutAllocation
LaborPositiveProfitButNoWorkerWhenPopBelow5
ParentFoodRequirement
PotentialParentCountWhenPopBelow5
PotentialParentWithReproductionGoodsWhenPopBelow5
PotentialParentFoodReadyWhenPopBelow5
ParentFoodGapWhenPopBelow5
ParentFoodGapWhenPopBelow3
LastIndividualsParentFoodGapAvg
FoodBoughtByPotentialParent
FoodAidToPotentialParent
BirthBlockedFoodSafetyWithReproductionGoods
```

## 测试

执行：

```bash
python3 -m py_compile *.py
python3 run_dev38_tests.py
```

### 结果摘要

5 人 × 1000 × 10 种子：

- 存活：0/10；
- 平均灭绝回合：174.7；
- 平均峰值人口：12.8；
- 货币守恒误差：0。

10 人 × 1000 × 10 种子：

- 存活：9/10；
- 平均最终人口：9.8；
- 平均峰值人口：24.5；
- 货币守恒误差：0。

## 关键发现

### 劳动转化

5 人低人口阶段平均：

- 原始劳动候选：3.2257；
- 被生产倾向裁掉：1.2931；
- 分配到劳动资源：1.9326；
- 实际劳动者：0.7178；
- 低人口且有正收益分公司但无实际劳动者：平均 7.6 回合；
- 无预期收益阻断累计：平均 26.0。

说明：低人口时不是完全没人愿意劳动。候选劳动者先被 `company_production_tendency` 裁掉一部分，之后仍有大量候选因分公司预期收益不足而未生产。

### 父代食物安全线

5 人低人口阶段平均：

- 潜在父代：2.3449；
- 已有生育用品的潜在父代：0.4517；
- 满足父代食物安全线的潜在父代：0.0；
- 父代食物缺口：79.3819；
- 最后 1–2 人阶段平均父代食物缺口：115.8743；
- 已有生育用品但因食物安全线阻断出生：平均 138.9 次。

说明：当前最明确的繁殖阻断不是“没有生育意愿”，而是已有或接近拥有生育用品的个体仍长期达不到 `survival_cost × 3` 的父代食物安全线。

## 下一步建议

1. 核查 `company_production_tendency` 的语义：它是否应该裁掉愿意劳动且有资源可分配的候选人，还是应只影响公司生产偏好/扩张规模；
2. 核查 `parent_food_required_for_birth = survival_cost × 3` 是否与 dev29 后“出生转移 child_initial_food + 新生儿不参与出生当回合生存消耗”形成重复保守；
3. 不建议直接提高工资、拉长寿命或加入人口恢复机制；
4. 下一版 dev39 可先做两组非默认实验：
   - company_production_tendency 不裁剪候选人，只影响生产权重；
   - parent_food_required_for_birth_multiplier 从 3 小幅测试 2.5 / 2，但不能直接作为默认值。

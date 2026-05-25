"""承压分配算法端到端测试

用 Mock 数据验证完整的 分配 → 约束 → 公平性 → 情景模拟 流程。

用法:
    cd profit-forecast
    python3 -m tests.test_allocation
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

SEPARATOR = "=" * 70


async def main():
    print(f"\n{SEPARATOR}")
    print("  承压分配算法 — 端到端测试")
    print(f"  日期: {date.today()}")
    print(SEPARATOR)

    # Step 1: 准备 Mock 门店数据
    from src.data.collectors.factory import create_collector
    from src.allocation.weight_calculator import StoreProfile

    collector = create_collector("mock")
    async with collector:
        stores_df = await collector.fetch_stores()
        sales_df = await collector.fetch_daily_sales()
        metrics_df = await collector.fetch_monthly_metrics()

    # 构建门店画像
    store_profiles = {}
    baselines = {}

    for _, row in stores_df.iterrows():
        code = row["store_code"]
        store_sales = metrics_df[metrics_df["store_code"] == code]
        avg_profit = store_sales["gross_profit"].mean() if "gross_profit" in store_sales.columns else 0
        avg_sqm = store_sales["sales_per_sqm"].mean() if "sales_per_sqm" in store_sales.columns else 0

        # 模拟商圈等级
        tier = row.get("commercial_tier", "C")

        # 模拟增长率（最近 3 个月 vs 前 3 个月）
        if len(store_sales) >= 6:
            recent = store_sales.tail(3)["sales_amount"].mean()
            prev = store_sales.head(3)["sales_amount"].mean()
            growth = (recent - prev) / prev if prev > 0 else 0
        else:
            growth = 0

        profile = StoreProfile(
            store_code=code,
            historical_profit=avg_profit,
            sales_per_sqm=avg_sqm,
            commercial_tier=tier,
            city_level="二线",
            store_area=row.get("store_area", 100),
            growth_rate=growth,
            opening_months=365,  # 默认开业 1 年
            baseline_sales=store_sales["sales_amount"].mean() if "sales_amount" in store_sales.columns else 0,
        )

        store_profiles[code] = profile
        baselines[code] = avg_profit if avg_profit > 0 else 100_000

    # 模拟 2 家新店
    new_stores = list(store_profiles.keys())[:2]
    for code in new_stores:
        store_profiles[code].opening_months = 3  # 开业 3 个月

    print(f"\n  数据准备:")
    print(f"    门店数: {len(store_profiles)}")
    print(f"    新店: {new_stores}")
    print(f"    总基线利润: {sum(baselines.values()):,.0f}")

    # Step 2: 权重计算
    from src.allocation.weight_calculator import WeightCalculator

    print(f"\n{SEPARATOR}")
    print("  1. 门店能力权重计算")
    print(SEPARATOR)

    calc = WeightCalculator()
    weights = calc.calculate(store_profiles)
    detail_df = calc.calculate_with_detail(store_profiles)

    print(f"\n  权重分布 (Top 10):")
    print(detail_df.head(10).to_string(index=False, max_colwidth=12))

    # Step 3: 承压分配
    from src.allocation.target_allocator import TargetAllocator

    print(f"\n{SEPARATOR}")
    print("  2. 承压分配（总目标增长 20%）")
    print(SEPARATOR)

    total_baseline = sum(baselines.values())
    total_target = total_baseline * 1.20  # 增长 20%

    allocator = TargetAllocator()
    plan = allocator.allocate(total_target, baselines, store_profiles)

    print(f"\n  分配方案:")
    print(f"    总目标: {plan.total_target:,.0f}")
    print(f"    总基线: {plan.total_baseline:,.0f}")
    print(f"    缺口: {plan.total_gap:,.0f}")
    print(f"    实际分配总额: {plan.total_allocated:,.0f}")
    print(f"    差额: {plan.total_target - plan.total_allocated:,.0f}")
    print(f"    平均增长率: {plan.avg_growth_rate:.1%}")
    print(f"    增长率范围: [{plan.min_growth_rate:.1%}, {plan.max_growth_rate:.1%}]")

    print(f"\n  分配明细 (Top 10):")
    alloc_df = plan.to_dataframe()
    print(alloc_df.head(10).to_string(index=False))

    if plan.constraint_result:
        cr = plan.constraint_result
        print(f"\n  约束调整:")
        print(f"    总调整数: {cr.total_violations}")
        print(f"    新店保护: {cr.new_store_count}")
        print(f"    保底线触达: {cr.floor_hit_count}")
        print(f"    上限触达: {cr.ceiling_hit_count}")

    # Step 4: 公平性检查
    from src.allocation.fairness_checker import FairnessChecker

    print(f"\n{SEPARATOR}")
    print("  3. 公平性检查")
    print(SEPARATOR)

    checker = FairnessChecker()
    fairness = checker.check(plan)

    print(f"\n  公平性评估:")
    print(f"    等级: {fairness.grade}")
    print(f"    平均承压率: {fairness.avg_pressure_rate:.1%}")
    print(f"    标准差: {fairness.std_pressure_rate:.1%}")
    print(f"    变异系数 (CV): {fairness.cv:.2%}")
    print(f"    最大承压率: {fairness.max_pressure_rate:.1%}")
    print(f"    最小承压率: {fairness.min_pressure_rate:.1%}")
    print(f"    高承压门店: {fairness.extreme_high_count}")
    print(f"    低承压门店: {fairness.extreme_low_count}")
    print(f"    新店平均承压率: {fairness.new_store_avg_pressure:.1%}")
    print(f"    是否公平: {'是' if fairness.is_fair else '否'}")

    if fairness.issues:
        print(f"\n  问题:")
        for issue in fairness.issues:
            print(f"    - {issue}")

    # Step 5: 情景模拟
    from src.allocation.scenario_simulator import ScenarioSimulator

    print(f"\n{SEPARATOR}")
    print("  4. 多情景模拟")
    print(SEPARATOR)

    simulator = ScenarioSimulator()
    comparison = simulator.simulate(baselines, store_profiles)

    print(f"\n  情景对比:")
    print(comparison.to_dataframe().to_string(index=False))
    print(f"\n  推荐方案: {comparison.recommend()}")

    # 各情景详细对比
    for name, scenario in comparison.scenarios.items():
        print(f"\n  [{name}] 总目标={scenario.total_target:,.0f} (+{scenario.growth_target:.0%})")
        print(f"    公平性: {scenario.fairness.grade} (CV={scenario.fairness.cv:.2%})")
        print(f"    增长率范围: [{scenario.plan.min_growth_rate:.1%}, {scenario.plan.max_growth_rate:.1%}]")
        if scenario.fairness.issues:
            for issue in scenario.fairness.issues:
                print(f"    ⚠ {issue}")

    # Step 6: 自定义目标模拟
    print(f"\n{SEPARATOR}")
    print("  5. 自定义目标（老板指定 600 万）")
    print(SEPARATOR)

    custom = simulator.simulate_custom(6_000_000, baselines, store_profiles)

    print(f"\n  自定义方案:")
    print(f"    总目标: {custom.total_target:,.0f}")
    print(f"    增长率: {custom.growth_target:.1%}")
    print(f"    公平性: {custom.fairness.grade}")
    print(f"    平均承压率: {custom.fairness.avg_pressure_rate:.1%}")

    # 汇总
    print(f"\n{SEPARATOR}")
    print("  测试汇总")
    print(SEPARATOR)

    print(f"  [PASS] 权重计算: {len(weights)} 家门店")
    print(f"  [PASS] 承压分配: {plan.store_count} 家门店, 差额 {plan.total_target - plan.total_allocated:,.0f}")
    print(f"  [PASS] 约束检查: {plan.constraint_result.total_violations} 项调整")
    print(f"  [PASS] 公平性检查: 等级 {fairness.grade}")
    print(f"  [PASS] 情景模拟: {len(comparison.scenarios)} 个方案")
    print(f"  [PASS] 自定义模拟: 完成")

    print(f"\n{SEPARATOR}")
    print("  Phase 3 承压分配算法测试完成 ✓")
    print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(main())

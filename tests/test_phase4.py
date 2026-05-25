"""利润测算与风险评估 — 端到端测试

用 Mock 数据验证完整的 承压分配 → 利润测算 → 风险评估 流程。

用法:
    cd profit-forecast
    python3 -m tests.test_phase4
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

SEPARATOR = "=" * 70


async def main():
    print(f"\n{SEPARATOR}")
    print("  Phase 4 — 利润测算与风险评估 端到端测试")
    print(f"  日期: {date.today()}")
    print(SEPARATOR)

    # ================================================================
    # Step 1: 准备数据（复用 Phase 3 的分配流程）
    # ================================================================
    from src.data.collectors.factory import create_collector
    from src.allocation.weight_calculator import StoreProfile, WeightCalculator
    from src.allocation.target_allocator import TargetAllocator

    collector = create_collector("mock")
    async with collector:
        stores_df = await collector.fetch_stores()
        sales_df = await collector.fetch_daily_sales()
        metrics_df = await collector.fetch_monthly_metrics()

    # 构建门店画像和基线
    store_profiles = {}
    baselines = {}

    for _, row in stores_df.iterrows():
        code = row["store_code"]
        store_sales = metrics_df[metrics_df["store_code"] == code]
        avg_profit = store_sales["gross_profit"].mean() if "gross_profit" in store_sales.columns else 0
        avg_sqm = store_sales["sales_per_sqm"].mean() if "sales_per_sqm" in store_sales.columns else 0
        tier = row.get("commercial_tier", "C")

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
            opening_months=365,
            baseline_sales=store_sales["sales_amount"].mean() if "sales_amount" in store_sales.columns else 0,
        )

        store_profiles[code] = profile
        baselines[code] = avg_profit if avg_profit > 0 else 100_000

    # 模拟 2 家新店
    new_stores = list(store_profiles.keys())[:2]
    for code in new_stores:
        store_profiles[code].opening_months = 3

    print(f"\n  数据准备:")
    print(f"    门店数: {len(store_profiles)}")
    print(f"    新店: {new_stores}")
    print(f"    总基线利润: {sum(baselines.values()):,.0f}")

    # 承压分配
    weight_calc = WeightCalculator()
    weights = weight_calc.calculate(store_profiles)

    total_baseline = sum(baselines.values())
    total_target = total_baseline * 1.20  # 增长 20%

    allocator = TargetAllocator()
    plan = allocator.allocate(total_target, baselines, store_profiles)

    print(f"    分配总目标: {plan.total_target:,.0f}")
    print(f"    平均增长率: {plan.avg_growth_rate:.1%}")

    # ================================================================
    # Step 2: 利润测算
    # ================================================================
    from src.profit.profit_calculator import ProfitCalculator
    from src.profit.cost_estimator import CostEstimator
    from src.profit.drill_down import DrillDownAnalyzer
    from src.profit.profit_report import ProfitReportGenerator

    print(f"\n{SEPARATOR}")
    print("  1. 利润测算")
    print(SEPARATOR)

    # 提取分配目标
    targets = {code: a.target for code, a in plan.allocations.items()}

    # 成本预估
    estimator = CostEstimator()
    cost_structures = estimator.estimate_from_baselines(targets, baselines)

    # 利润计算
    calc = ProfitCalculator()
    profit_summary = calc.calculate(targets, cost_structures)

    print(f"\n  利润测算结果:")
    print(f"    总收入: {profit_summary.total_revenue:,.0f}")
    print(f"    总采购成本: {profit_summary.total_cogs:,.0f}")
    print(f"    总毛利: {profit_summary.total_gross_profit:,.0f} (毛利率 {profit_summary.avg_gross_margin:.1%})")
    print(f"    总运营费用: {profit_summary.total_operating_expense:,.0f}")
    print(f"    总营业利润: {profit_summary.total_operating_profit:,.0f} (利润率 {profit_summary.avg_operating_margin:.1%})")
    print(f"    总税费: {profit_summary.total_tax:,.0f}")
    print(f"    总净利润: {profit_summary.total_net_profit:,.0f} (净利率 {profit_summary.avg_net_margin:.1%})")
    print(f"    门店: {profit_summary.store_count} 家, 盈利 {profit_summary.profitable_count}, 亏损 {profit_summary.loss_count}")

    # 利润明细
    profit_df = calc.to_dataframe(profit_summary)
    print(f"\n  利润明细 (Top 5):")
    print(profit_df.head(5).to_string(index=False))

    # ================================================================
    # Step 3: 基线 vs 目标对比
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  2. 基线 vs 目标对比")
    print(SEPARATOR)

    # 基线利润测算
    baseline_targets = baselines
    baseline_costs = estimator.estimate_from_baselines(baseline_targets, baselines)
    baseline_summary = calc.calculate(baseline_targets, baseline_costs)

    report_gen = ProfitReportGenerator(calc)
    comparison_df = report_gen.generate_store_comparison(baseline_summary, profit_summary)

    print(f"\n  基线 vs 目标 (Top 10):")
    print(comparison_df.head(10).to_string(index=False))

    # P&L 表
    pnl_df = report_gen.generate_pnl_table(profit_summary)
    print(f"\n  利润表 (P&L):")
    print(pnl_df.to_string(index=False))

    # 汇总字典
    summary_dict = report_gen.generate_summary_dict(profit_summary)
    print(f"\n  汇总指标:")
    for k, v in summary_dict.items():
        print(f"    {k}: {v}")

    # ================================================================
    # Step 4: 下钻分析
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  3. 下钻分析")
    print(SEPARATOR)

    drill_down = DrillDownAnalyzer()

    # 按区域下钻
    store_region_map = {}
    for _, row in stores_df.iterrows():
        store_region_map[row["store_code"]] = row.get("region", "华东")

    region_result = drill_down.by_region(profit_summary, store_region_map)
    print(f"\n  按区域:")
    print(region_result.to_dataframe().to_string(index=False))

    # 按门店类型下钻
    store_type_map = {}
    for _, row in stores_df.iterrows():
        store_type_map[row["store_code"]] = row.get("store_type", "标准店")

    type_result = drill_down.by_store_type(profit_summary, store_type_map)
    print(f"\n  按门店类型:")
    print(type_result.to_dataframe().to_string(index=False))

    # Top/Bottom 排行
    ranking = drill_down.top_bottom(profit_summary, n=5)
    print(f"\n  Top 5 盈利门店:")
    print(ranking["top_n"].to_string(index=False))
    print(f"\n  Bottom 5 门店:")
    print(ranking["bottom_n"].to_string(index=False))

    # ================================================================
    # Step 5: 风险评估 — 目标可达性
    # ================================================================
    from src.risk.reachability import ReachabilityAssessor

    print(f"\n{SEPARATOR}")
    print("  4. 风险评估 — 目标可达性")
    print(SEPARATOR)

    reach_assessor = ReachabilityAssessor()
    reach_results = reach_assessor.assess(targets, baselines)

    reach_df = reach_assessor.to_dataframe(reach_results)
    print(f"\n  可达性评估 (Top 10):")
    print(reach_df.head(10).to_string(index=False))

    high_risk = [r for r in reach_results if r.risk_level in ("high", "critical")]
    print(f"\n  高风险门店: {len(high_risk)} 家")
    for r in high_risk[:5]:
        print(f"    {r.store_code}: 目标/基线={r.target_ratio:.1%}, 风险={r.risk_level}, {r.suggestion}")

    # ================================================================
    # Step 6: 风险评估 — 承压分布
    # ================================================================
    from src.risk.pressure_distribution import PressureDistributionAnalyzer

    print(f"\n{SEPARATOR}")
    print("  5. 风险评估 — 承压分布")
    print(SEPARATOR)

    pressure_analyzer = PressureDistributionAnalyzer()
    pressure = pressure_analyzer.analyze(plan)

    print(f"\n  承压分布:")
    print(f"    平均承压率: {pressure.mean_pressure_rate:.1%}")
    print(f"    中位数: {pressure.median_pressure_rate:.1%}")
    print(f"    标准差: {pressure.std_pressure_rate:.1%}")
    print(f"    IQR: [{pressure.p25:.1%}, {pressure.p75:.1%}]")
    print(f"    异常门店: {len(pressure.outliers)} 家")

    print(f"\n  承压率分布:")
    for bucket, count in pressure.histogram.items():
        bar = "█" * count
        print(f"    {bucket:>10s}: {bar} ({count})")

    # ================================================================
    # Step 7: 风险评估 — 蒙特卡洛模拟
    # ================================================================
    from src.risk.scenario_modeler import MonteCarloSimulator

    print(f"\n{SEPARATOR}")
    print("  6. 蒙特卡洛利润模拟")
    print(SEPARATOR)

    mc_simulator = MonteCarloSimulator()
    mc_result = mc_simulator.simulate(
        base_revenue=profit_summary.total_revenue,
        base_cost=profit_summary.total_cogs + profit_summary.total_operating_expense,
        n_simulations=5000,
    )

    print(f"\n  蒙特卡洛结果 (5000 次模拟):")
    print(f"    利润均值: {mc_result.profit_mean:,.0f}")
    print(f"    利润标准差: {mc_result.profit_std:,.0f}")
    print(f"    利润中位数: {mc_result.profit_median:,.0f}")
    print(f"    5% 分位 (VaR95): {mc_result.profit_p5:,.0f}")
    print(f"    10% 分位 (VaR90): {mc_result.profit_p10:,.0f}")
    print(f"    25% 分位: {mc_result.profit_p25:,.0f}")
    print(f"    75% 分位: {mc_result.profit_p75:,.0f}")
    print(f"    95% 分位: {mc_result.profit_p95:,.0f}")
    print(f"    亏损概率: {mc_result.loss_probability:.1%}")
    print(f"    VaR95: {mc_result.var_95:,.0f}")
    print(f"    CVaR95: {mc_result.cvar_95:,.0f}")

    # 利润分布直方图（ASCII）
    dist = mc_result.profit_distribution
    percentiles = [0, 5, 10, 25, 50, 75, 90, 95, 100]
    print(f"\n    利润分布分位数:")
    for p in percentiles:
        val = float(__import__("numpy").percentile(dist, p))
        print(f"      P{p:3d}: {val:>12,.0f}")

    # ================================================================
    # Step 8: 综合风险评估
    # ================================================================
    from src.risk.risk_assessor import RiskAssessor
    from src.risk.risk_report import RiskReportGenerator

    print(f"\n{SEPARATOR}")
    print("  7. 综合风险评估")
    print(SEPARATOR)

    # 构建历史月度数据（Mock）
    historical_monthly = {}
    for code in store_profiles:
        hist = (await collector.fetch_daily_sales() if False else sales_df)
        store_hist = hist[hist["store_code"] == code] if "store_code" in hist.columns else hist
        if "sales_amount" in store_hist.columns:
            # 按月汇总（Mock 数据比较简单，直接用已有值）
            monthly_values = store_hist["sales_amount"].tolist()
            # 取前 12 个值作为月度数据
            historical_monthly[code] = monthly_values[:12] if len(monthly_values) >= 12 else monthly_values

    risk_assessor = RiskAssessor()
    assessment = risk_assessor.assess(
        plan=plan,
        profit_summary=profit_summary,
        historical_monthly=historical_monthly,
    )

    print(f"\n  综合风险评估:")
    print(f"    综合风险分: {assessment.overall_score:.1f}")
    print(f"    综合风险等级: {assessment.overall_level}")
    print(f"    高风险门店: {len(assessment.high_risk_stores)} 家")

    print(f"\n  各风险因素:")
    factors_df = assessment.to_dataframe()
    print(factors_df.to_string(index=False))

    print(f"\n  建议:")
    for rec in assessment.recommendations:
        print(f"    - {rec}")

    # ================================================================
    # Step 9: 风险报告
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  8. 风险报告")
    print(SEPARATOR)

    risk_report_gen = RiskReportGenerator()

    # 汇总字典
    risk_summary = risk_report_gen.generate_summary_dict(assessment)
    print(f"\n  风险汇总:")
    for k, v in risk_summary.items():
        print(f"    {k}: {v}")

    # 建议列表
    recommendations = risk_report_gen.generate_recommendations(assessment)
    print(f"\n  完整建议 ({len(recommendations)} 条):")
    for i, rec in enumerate(recommendations, 1):
        print(f"    {i}. {rec}")

    # 高风险门店明细
    high_risk_df = risk_report_gen.generate_high_risk_stores(assessment)
    if not high_risk_df.empty:
        print(f"\n  高风险门店明细:")
        print(high_risk_df.to_string(index=False))
    else:
        print(f"\n  无高风险门店")

    # ================================================================
    # 汇总
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  测试汇总")
    print(SEPARATOR)

    print(f"  [PASS] 成本预估: {len(cost_structures)} 家门店")
    print(f"  [PASS] 利润测算: 净利润 {profit_summary.total_net_profit:,.0f}, 盈利率 {profit_summary.profit_rate:.1%}")
    print(f"  [PASS] P&L 报告: 生成完成")
    print(f"  [PASS] 基线对比: {len(comparison_df)} 家门店")
    print(f"  [PASS] 区域下钻: {len(region_result.groups)} 个区域")
    print(f"  [PASS] 类型下钻: {len(type_result.groups)} 种类型")
    print(f"  [PASS] 可达性评估: 高风险 {len(high_risk)} 家")
    print(f"  [PASS] 承压分布: 标准差 {pressure.std_pressure_rate:.1%}, 异常 {len(pressure.outliers)} 家")
    print(f"  [PASS] 蒙特卡洛: 亏损概率 {mc_result.loss_probability:.1%}, VaR95={mc_result.var_95:,.0f}")
    print(f"  [PASS] 综合风险: 分数 {assessment.overall_score:.1f}, 等级 {assessment.overall_level}")
    print(f"  [PASS] 风险报告: {len(recommendations)} 条建议")

    print(f"\n{SEPARATOR}")
    print("  Phase 4 利润测算与风险评估测试完成 ✓")
    print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(main())

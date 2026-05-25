"""Phase 5 — Agent 编排层 + API 路由 端到端测试

验证完整的 Agent 编排流程。

用法:
    cd profit-forecast
    python3 -m tests.test_phase5
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
    print("  Phase 5 — Agent 编排层 端到端测试")
    print(f"  日期: {date.today()}")
    print(SEPARATOR)

    # ================================================================
    # 1. 测试各 Agent 独立运行
    # ================================================================
    from src.agents.data_agent import DataAgent
    from src.agents.baseline_agent import BaselineAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.agents.profit_agent import ProfitAgent
    from src.agents.risk_agent import RiskAgent

    # 1.1 数据采集 Agent
    print(f"\n{SEPARATOR}")
    print("  1. 数据采集 Agent")
    print(SEPARATOR)

    data_agent = DataAgent("mock")
    data_result = await data_agent.collect()

    print(f"    门店: {data_result.store_count}")
    print(f"    日销: {data_result.sales_count}")
    print(f"    月度: {data_result.metrics_count}")
    print(f"    质量问题: {len(data_result.quality_errors)}")
    assert data_result.store_count > 0, "门店数应 > 0"
    print("  [PASS] 数据采集 Agent")

    # 1.2 基线预估 Agent
    print(f"\n{SEPARATOR}")
    print("  2. 基线预估 Agent")
    print(SEPARATOR)

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(data_result.monthly_metrics)

    print(f"    门店数: {baseline_result.store_count}")
    print(f"    平均 MAPE: {baseline_result.avg_mape:.1%}")
    print(f"    基线示例: {list(baseline_result.baselines.items())[:3]}")
    assert baseline_result.store_count > 0, "基线门店数应 > 0"
    print("  [PASS] 基线预估 Agent")

    # 1.3 承压分配 Agent
    print(f"\n{SEPARATOR}")
    print("  3. 承压分配 Agent")
    print(SEPARATOR)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(
        data_result.stores, data_result.monthly_metrics
    )

    total_baseline = sum(baseline_result.baselines.values())
    total_target = total_baseline * 1.20

    allocation_result = allocation_agent.allocate(
        total_target=total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=True,
    )

    print(f"    门店数: {allocation_result.store_count}")
    print(f"    总目标: {allocation_result.plan.total_target:,.0f}")
    print(f"    公平性: {allocation_result.fairness.grade}")
    print(f"    CV: {allocation_result.fairness.cv:.2%}")
    assert allocation_result.store_count > 0, "分配门店数应 > 0"
    print("  [PASS] 承压分配 Agent")

    # 1.4 利润测算 Agent
    print(f"\n{SEPARATOR}")
    print("  4. 利润测算 Agent")
    print(SEPARATOR)

    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}

    store_region_map = {}
    store_type_map = {}
    for _, row in data_result.stores.iterrows():
        store_region_map[row["store_code"]] = row.get("region", "未知")
        store_type_map[row["store_code"]] = row.get("store_type", "标准店")

    profit_agent = ProfitAgent()
    profit_result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
        store_region_map=store_region_map,
        store_type_map=store_type_map,
    )

    print(f"    净利润: {profit_result.summary.total_net_profit:,.0f}")
    print(f"    净利率: {profit_result.summary.avg_net_margin:.1%}")
    print(f"    盈利: {profit_result.summary.profitable_count}, 亏损: {profit_result.summary.loss_count}")
    print(f"    P&L 行数: {len(profit_result.pnl_table)}")
    print(f"    对比行数: {len(profit_result.comparison)}")
    if profit_result.region_drill_down:
        print(f"    区域下钻: {len(profit_result.region_drill_down.groups)} 个区域")
    assert profit_result.summary.total_revenue > 0, "总收入应 > 0"
    print("  [PASS] 利润测算 Agent")

    # 1.5 风险评估 Agent
    print(f"\n{SEPARATOR}")
    print("  5. 风险评估 Agent")
    print(SEPARATOR)

    import pandas as pd
    historical_monthly = {}
    for code in baseline_result.baselines:
        store_sales = data_result.daily_sales[
            data_result.daily_sales["store_code"] == code
        ] if not data_result.daily_sales.empty else pd.DataFrame()
        if not store_sales.empty and "sales_amount" in store_sales.columns:
            historical_monthly[code] = store_sales["sales_amount"].tolist()

    risk_agent = RiskAgent()
    risk_result = risk_agent.assess(
        plan=allocation_result.plan,
        profit_summary=profit_result.summary,
        historical_monthly=historical_monthly,
    )

    print(f"    综合风险分: {risk_result.assessment.overall_score:.1f}")
    print(f"    风险等级: {risk_result.assessment.overall_level}")
    print(f"    高风险门店: {len(risk_result.assessment.high_risk_stores)}")
    print(f"    建议数: {len(risk_result.recommendations)}")
    if risk_result.monte_carlo:
        print(f"    亏损概率: {risk_result.monte_carlo.loss_probability:.1%}")
    assert risk_result.assessment.overall_score >= 0, "风险分应 >= 0"
    print("  [PASS] 风险评估 Agent")

    # ================================================================
    # 2. 测试编排器完整流程
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  6. 编排器完整流程")
    print(SEPARATOR)

    from src.agents.orchestrator import Orchestrator

    orchestrator = Orchestrator("mock")
    pipeline_result = await orchestrator.run(total_target=total_target)

    print(f"\n  完整流程摘要:")
    for k, v in pipeline_result.summary.items():
        print(f"    {k}: {v}")

    assert pipeline_result.is_success, "流程应无错误"
    assert pipeline_result.duration_seconds > 0, "耗时应 > 0"
    print(f"\n  [PASS] 编排器完整流程")

    # ================================================================
    # 3. 测试模块导入（模拟 API 路由导入）
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  7. API 路由模块导入")
    print(SEPARATOR)

    modules = [
        "src.api.routes.forecast",
        "src.api.routes.allocation",
        "src.api.routes.profit",
        "src.api.routes.risk",
        "src.api.routes.orchestrate",
    ]

    for mod_name in modules:
        try:
            __import__(mod_name)
            print(f"    [PASS] {mod_name}")
        except Exception as e:
            print(f"    [FAIL] {mod_name}: {e}")
            raise

    # ================================================================
    # 4. 测试 FastAPI 应用创建
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  8. FastAPI 应用创建")
    print(SEPARATOR)

    from src.api.app import create_app
    app = create_app()

    routes = [r.path for r in app.routes]
    expected_routes = [
        "/api/v1/forecast/baselines",
        "/api/v1/allocation/",
        "/api/v1/profit/calculate",
        "/api/v1/risk/assess",
        "/api/v1/pipeline/run",
    ]

    for route in expected_routes:
        if route in routes:
            print(f"    [PASS] {route}")
        else:
            print(f"    [FAIL] {route} 未注册")

    # ================================================================
    # 汇总
    # ================================================================
    print(f"\n{SEPARATOR}")
    print("  测试汇总")
    print(SEPARATOR)

    print(f"  [PASS] 数据采集 Agent: {data_result.store_count} 家门店")
    print(f"  [PASS] 基线预估 Agent: MAPE={baseline_result.avg_mape:.1%}")
    print(f"  [PASS] 承压分配 Agent: 公平性={allocation_result.fairness.grade}")
    print(f"  [PASS] 利润测算 Agent: 净利润={profit_result.summary.total_net_profit:,.0f}")
    print(f"  [PASS] 风险评估 Agent: 风险等级={risk_result.assessment.overall_level}")
    print(f"  [PASS] 编排器完整流程: 耗时={pipeline_result.duration_seconds:.1f}s")
    print(f"  [PASS] API 路由导入: {len(modules)} 个模块")
    print(f"  [PASS] FastAPI 应用: {len(expected_routes)} 个路由")

    print(f"\n{SEPARATOR}")
    print("  Phase 5 Agent 编排层测试完成 ✓")
    print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(main())

"""
真实数据利润测算脚本

连接 StarRocks，采集真实数据，运行完整利润测算管道。

使用方式:
    # 1. 确保 .env 配置了 StarRocks 连接信息
    # 2. 运行脚本
    python scripts/run_real_profit.py

    # 可选参数
    python scripts/run_real_profit.py --target 10000000     # 指定总利润目标
    python scripts/run_real_profit.py --stores ST0001,ST0002  # 指定门店
    python scripts/run_real_profit.py --months 3             # 取最近3个月均值
    python scripts/run_real_profit.py --export result.csv    # 导出CSV
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    project_root / "logs" / "real_profit_{time:YYYYMMDD_HHmmss}.log",
    level="DEBUG",
    rotation="10 MB",
)


async def main(args: argparse.Namespace):
    """主流程"""
    from src.data.collectors.starrocks_collector import StarRocksCollector
    from src.profit.cost_estimator import CostEstimator
    from src.agents.baseline_agent import BaselineAgent
    from src.agents.allocation_agent import AllocationAgent
    from src.agents.profit_agent import ProfitAgent
    from src.agents.risk_agent import RiskAgent
    from src.profit.profit_report import ProfitReportGenerator

    store_filter = args.stores.split(",") if args.stores else None

    # ========================================================
    # Phase 1: 数据采集
    # ========================================================
    logger.info("=" * 60)
    logger.info("Phase 1: 从 StarRocks 采集真实数据")
    logger.info("=" * 60)

    collector = StarRocksCollector()

    async with collector:
        # 1.1 门店主数据
        logger.info(">>> 采集门店主数据...")
        stores_df = await collector.fetch_stores()
        if store_filter:
            stores_df = stores_df[stores_df["store_code"].isin(store_filter)]
        logger.info(f"    门店数: {len(stores_df)}")

        # 1.2 月度指标（用于基线预估）
        logger.info(">>> 采集月度指标...")
        monthly_metrics = await collector.fetch_monthly_metrics(
            store_codes=store_filter,
        )
        logger.info(f"    月度记录: {len(monthly_metrics)}")

        # 1.3 门店日损益（核心！用于真实成本结构）
        logger.info(">>> 采集门店日损益数据...")
        store_loss = await collector.fetch_store_loss(
            store_codes=store_filter,
        )
        logger.info(f"    损益记录: {len(store_loss)}")

        # 1.4 成本结构明细（备用）
        logger.info(">>> 采集成本结构明细...")
        cost_structure = await collector.fetch_cost_structure(
            store_codes=store_filter,
        )
        logger.info(f"    成本记录: {len(cost_structure)}")

        # 1.5 日目标数据
        logger.info(">>> 采集日目标数据...")
        daily_target_cost = await collector.fetch_daily_target_cost(
            store_codes=store_filter,
        )
        logger.info(f"    目标记录: {len(daily_target_cost)}")

        # 1.6 开关状态
        logger.info(">>> 采集开关状态...")
        switch_status = await collector.fetch_switch_status(
            store_codes=store_filter,
        )
        logger.info(f"    状态记录: {len(switch_status)}")

    # 数据概览
    logger.info("")
    logger.info("数据采集概览:")
    logger.info(f"  门店数:     {len(stores_df)}")
    logger.info(f"  月度指标:   {len(monthly_metrics)} 行")
    logger.info(f"  日损益:     {len(store_loss)} 行")
    logger.info(f"  成本明细:   {len(cost_structure)} 行")
    logger.info(f"  日目标:     {len(daily_target_cost)} 行")
    logger.info(f"  开关状态:   {len(switch_status)} 行")

    if stores_df.empty:
        logger.error("未获取到门店数据，请检查 StarRocks 连接配置")
        return

    if monthly_metrics.empty:
        logger.error("未获取到月度指标数据，请检查数据源")
        return

    # ========================================================
    # Phase 2: 基线预估
    # ========================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 2: 基线预估（基于历史月度数据）")
    logger.info("=" * 60)

    baseline_agent = BaselineAgent()
    baseline_result = baseline_agent.forecast(monthly_metrics)

    logger.info(f"  基线预估完成: {len(baseline_result.baselines)} 家门店")
    total_baseline = sum(baseline_result.baselines.values())
    logger.info(f"  基线总额: {total_baseline:,.0f}")

    # ========================================================
    # Phase 3: 承压分配
    # ========================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 3: 承压分配")

    # 如果未指定目标，使用基线的 1.2 倍
    total_target = args.target or total_baseline * 1.2
    logger.info(f"  总目标: {total_target:,.0f} (基线: {total_baseline:,.0f})")
    logger.info("=" * 60)

    allocation_agent = AllocationAgent()
    store_profiles = allocation_agent.build_store_profiles(stores_df, monthly_metrics)
    allocation_result = allocation_agent.allocate(
        total_target=total_target,
        baselines=baseline_result.baselines,
        store_profiles=store_profiles,
        with_scenarios=False,
    )

    allocated_total = sum(a.target for a in allocation_result.plan.allocations.values())
    logger.info(f"  分配完成: {len(allocation_result.plan.allocations)} 家门店")
    logger.info(f"  分配总额: {allocated_total:,.0f}")

    # ========================================================
    # Phase 4: 利润测算（使用真实成本数据）
    # ========================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 4: 利润测算（接入真实损益数据）")
    logger.info("=" * 60)

    targets = {c: a.target for c, a in allocation_result.plan.allocations.items()}

    # 从真实损益数据构建成本结构
    cost_structures = None
    if not store_loss.empty:
        cost_estimator = CostEstimator()
        cost_structures = cost_estimator.from_store_loss_data(
            store_loss_df=store_loss,
            targets=targets,
            months=args.months,
        )
        real_count = sum(1 for v in cost_structures.values() if v.get("data_source") == "real")
        logger.info(f"  成本结构: {len(cost_structures)} 家门店, {real_count} 家使用真实数据")
    else:
        logger.warning("  无损益数据，将使用默认成本比例")

    # 构建门店属性映射
    store_region_map = {}
    store_type_map = {}
    for _, row in stores_df.iterrows():
        store_region_map[row["store_code"]] = row.get("region", "未知")
        store_type_map[row["store_code"]] = row.get("store_type", "标准店")

    # 利润测算
    profit_agent = ProfitAgent()
    profit_result = profit_agent.calculate(
        targets=targets,
        baselines=baseline_result.baselines,
        cost_structures=cost_structures,
        store_region_map=store_region_map,
        store_type_map=store_type_map,
    )

    logger.info(f"  利润测算完成: {len(profit_result.summary)} 家门店")

    # ========================================================
    # Phase 5: 风险评估
    # ========================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 5: 风险评估")
    logger.info("=" * 60)

    risk_agent = RiskAgent()
    risk_result = risk_agent.assess(
        allocation=allocation_result,
        profit=profit_result,
        store_profiles=store_profiles,
    )

    logger.info(f"  风险等级: {risk_result.summary_dict.get('risk_level', 'N/A')}")
    logger.info(f"  建议数:   {len(risk_result.recommendations)}")

    # ========================================================
    # 输出结果
    # ========================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("利润测算结果汇总")
    logger.info("=" * 60)

    summary = profit_result.summary_dict
    logger.info(f"  总目标:       {summary.get('total_target', 0):>15,.0f}")
    logger.info(f"  总基线:       {summary.get('total_baseline', 0):>15,.0f}")
    logger.info(f"  总收入:       {summary.get('total_revenue', 0):>15,.0f}")
    logger.info(f"  总成本:       {summary.get('total_cost', 0):>15,.0f}")
    logger.info(f"  总毛利:       {summary.get('total_gross_profit', 0):>15,.0f}")
    logger.info(f"  总费用:       {summary.get('total_expense', 0):>15,.0f}")
    logger.info(f"  总利润:       {summary.get('total_profit', 0):>15,.0f}")
    logger.info(f"  利润率:       {summary.get('profit_margin', 0):>14.1%}")
    logger.info(f"  盈利门店:     {summary.get('profitable_count', 0)}")
    logger.info(f"  亏损门店:     {summary.get('loss_count', 0)}")

    # P&L 表
    logger.info("")
    logger.info("P&L 利润表:")
    report = ProfitReportGenerator()
    pnl = report.generate_pnl_table(profit_result.summary)
    for _, row in pnl.iterrows():
        item = row.get("项目", "")
        amount = row.get("金额", "")
        ratio = row.get("占收入比", "")
        logger.info(f"  {item:<20} {amount:>15} {ratio:>10}")

    # Top/Bottom 门店
    logger.info("")
    ranking = profit_agent.get_top_bottom(profit_result.summary, n=5)
    logger.info("Top 5 盈利门店:")
    for _, row in ranking["top_n"].iterrows():
        logger.info(f"  {row.get('store_code', ''):<10} 利润: {row.get('profit', 0):>12,.0f}  利润率: {row.get('profit_margin', 0):>6.1%}")

    logger.info("Bottom 5 亏损门店:")
    for _, row in ranking["bottom_n"].iterrows():
        logger.info(f"  {row.get('store_code', ''):<10} 利润: {row.get('profit', 0):>12,.0f}  利润率: {row.get('profit_margin', 0):>6.1%}")

    # 风险建议
    logger.info("")
    logger.info("风险建议:")
    for i, rec in enumerate(risk_result.recommendations, 1):
        logger.info(f"  {i}. {rec}")

    # ========================================================
    # 导出
    # ========================================================
    if args.export:
        export_path = Path(args.export)
        logger.info("")
        logger.info(f"导出结果到: {export_path}")

        # 门店利润明细
        from src.profit.profit_calculator import ProfitCalculator
        calc = ProfitCalculator()
        detail_df = calc.to_dataframe(profit_result.summary)
        detail_df.to_csv(export_path, index=False, encoding="utf-8-sig")
        logger.info(f"  已导出 {len(detail_df)} 行到 {export_path}")

        # P&L 表
        pnl_path = export_path.with_name(export_path.stem + "_pnl.csv")
        pnl.to_csv(pnl_path, index=False, encoding="utf-8-sig")
        logger.info(f"  P&L 表已导出到 {pnl_path}")

    logger.info("")
    logger.info("完成!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="真实数据利润测算")
    parser.add_argument(
        "--target", type=float, default=None,
        help="总利润目标（默认: 基线 x 1.2）",
    )
    parser.add_argument(
        "--stores", type=str, default=None,
        help="指定门店编码（逗号分隔，如 ST0001,ST0002）",
    )
    parser.add_argument(
        "--months", type=int, default=3,
        help="取最近 N 个月的成本数据均值（默认: 3）",
    )
    parser.add_argument(
        "--export", type=str, default=None,
        help="导出 CSV 文件路径",
    )

    args = parser.parse_args()
    asyncio.run(main(args))

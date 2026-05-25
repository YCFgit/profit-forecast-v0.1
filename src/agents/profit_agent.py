"""利润测算 Agent

负责计算各门店和整体的利润。
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.profit.profit_calculator import ProfitCalculator, ProfitSummary
from src.profit.cost_estimator import CostEstimator
from src.profit.drill_down import DrillDownAnalyzer, DrillDownResult
from src.profit.profit_report import ProfitReportGenerator


@dataclass
class ProfitResult:
    """利润测算结果"""
    summary: ProfitSummary
    baseline_summary: ProfitSummary | None = None
    pnl_table: pd.DataFrame | None = None
    comparison: pd.DataFrame | None = None
    region_drill_down: DrillDownResult | None = None
    type_drill_down: DrillDownResult | None = None
    summary_dict: dict | None = None


class ProfitAgent:
    """利润测算 Agent

    使用方式：
        agent = ProfitAgent()
        result = agent.calculate(targets, baselines, cost_structures)
    """

    def __init__(self):
        self.calculator = ProfitCalculator()
        self.cost_estimator = CostEstimator()
        self.drill_down = DrillDownAnalyzer()
        self.report_gen = ProfitReportGenerator()

    def calculate(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        cost_structures: dict[str, dict[str, float]] | None = None,
        store_region_map: dict[str, str] | None = None,
        store_type_map: dict[str, str] | None = None,
    ) -> ProfitResult:
        """执行利润测算

        Args:
            targets: {门店编码: 目标收入}
            baselines: {门店编码: 基线收入}
            cost_structures: {门店编码: 成本明细}，None 则自动估算
            store_region_map: {门店编码: 区域}
            store_type_map: {门店编码: 门店类型}

        Returns:
            ProfitResult
        """
        # 成本预估（如未提供）
        if cost_structures is None:
            cost_structures = self.cost_estimator.estimate_from_baselines(targets, baselines)
            logger.info("使用基线估算成本结构（默认比例）")
        else:
            real_count = sum(1 for v in cost_structures.values() if v.get("data_source") == "real")
            logger.info(
                f"使用真实损益数据: {len(cost_structures)} 家门店, "
                f"{real_count} 家使用真实数据"
            )

        # 目标利润测算
        summary = self.calculator.calculate(targets, cost_structures)

        # 基线利润测算（用于对比）
        baseline_costs = self.cost_estimator.estimate_from_baselines(baselines, baselines)
        baseline_summary = self.calculator.calculate(baselines, baseline_costs)

        # P&L 表
        pnl_table = self.report_gen.generate_pnl_table(summary)

        # 基线 vs 目标对比
        comparison = self.report_gen.generate_store_comparison(baseline_summary, summary)

        # 下钻分析
        region_drill_down = None
        if store_region_map:
            region_drill_down = self.drill_down.by_region(summary, store_region_map)

        type_drill_down = None
        if store_type_map:
            type_drill_down = self.drill_down.by_store_type(summary, store_type_map)

        # 汇总字典
        summary_dict = self.report_gen.generate_summary_dict(summary)

        result = ProfitResult(
            summary=summary,
            baseline_summary=baseline_summary,
            pnl_table=pnl_table,
            comparison=comparison,
            region_drill_down=region_drill_down,
            type_drill_down=type_drill_down,
            summary_dict=summary_dict,
        )

        logger.info(
            f"利润测算完成: 净利润={summary.total_net_profit:,.0f}, "
            f"净利率={summary.avg_net_margin:.1%}, "
            f"盈利={summary.profitable_count}, 亏损={summary.loss_count}"
        )

        return result

    def calculate_with_custom_costs(
        self,
        targets: dict[str, float],
        cost_structures: dict[str, dict[str, float]],
    ) -> ProfitSummary:
        """使用自定义成本结构测算利润"""
        return self.calculator.calculate(targets, cost_structures)

    def get_top_bottom(
        self,
        summary: ProfitSummary,
        n: int = 10,
    ) -> dict[str, pd.DataFrame]:
        """获取 Top/Bottom 门店排行"""
        return self.drill_down.top_bottom(summary, n)

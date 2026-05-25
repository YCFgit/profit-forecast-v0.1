"""风险评估 Agent

负责综合评估承压分配方案的风险。
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.allocation.target_allocator import AllocationPlan
from src.profit.profit_calculator import ProfitSummary
from src.risk.risk_assessor import RiskAssessor, RiskAssessment
from src.risk.reachability import ReachabilityAssessor, ReachabilityResult
from src.risk.pressure_distribution import PressureDistributionAnalyzer, PressureDistributionResult
from src.risk.scenario_modeler import MonteCarloSimulator, MonteCarloResult
from src.risk.risk_report import RiskReportGenerator


@dataclass
class RiskResult:
    """风险评估结果"""
    assessment: RiskAssessment
    reachability: list[ReachabilityResult]
    pressure: PressureDistributionResult
    monte_carlo: MonteCarloResult | None
    recommendations: list[str]
    summary_dict: dict
    high_risk_stores: pd.DataFrame


class RiskAgent:
    """风险评估 Agent

    使用方式：
        agent = RiskAgent()
        result = agent.assess(plan, profit_summary, historical_monthly)
    """

    def __init__(self):
        self.assessor = RiskAssessor()
        self.reachability_assessor = ReachabilityAssessor()
        self.pressure_analyzer = PressureDistributionAnalyzer()
        self.mc_simulator = MonteCarloSimulator()
        self.report_gen = RiskReportGenerator()

    def assess(
        self,
        plan: AllocationPlan,
        profit_summary: ProfitSummary | None = None,
        historical_monthly: dict[str, list[float]] | None = None,
    ) -> RiskResult:
        """执行综合风险评估

        Args:
            plan: 承压分配方案
            profit_summary: 利润测算结果
            historical_monthly: 历史月度数据

        Returns:
            RiskResult
        """
        # 综合风险评估
        assessment = self.assessor.assess(plan, profit_summary, historical_monthly)

        # 详细分析
        targets = {c: a.target for c, a in plan.allocations.items()}
        baselines = {c: a.baseline for c, a in plan.allocations.items()}

        reachability = self.reachability_assessor.assess(targets, baselines, historical_monthly)
        pressure = self.pressure_analyzer.analyze(plan)

        # 蒙特卡洛模拟
        mc_result = None
        if profit_summary:
            mc_result = self.mc_simulator.simulate(
                base_revenue=profit_summary.total_revenue,
                base_cost=profit_summary.total_cogs + profit_summary.total_operating_expense,
                n_simulations=5000,
            )

        # 报告
        recommendations = self.report_gen.generate_recommendations(assessment)
        summary_dict = self.report_gen.generate_summary_dict(assessment)
        high_risk_stores = self.report_gen.generate_high_risk_stores(assessment)

        result = RiskResult(
            assessment=assessment,
            reachability=reachability,
            pressure=pressure,
            monte_carlo=mc_result,
            recommendations=recommendations,
            summary_dict=summary_dict,
            high_risk_stores=high_risk_stores,
        )

        logger.info(
            f"风险评估完成: 综合分={assessment.overall_score:.1f}, "
            f"等级={assessment.overall_level}, "
            f"高风险门店={len(assessment.high_risk_stores)}"
        )

        return result

    def assess_reachability_only(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        historical_monthly: dict[str, list[float]] | None = None,
    ) -> list[ReachabilityResult]:
        """仅评估目标可达性"""
        return self.reachability_assessor.assess(targets, baselines, historical_monthly)

    def simulate_monte_carlo(
        self,
        base_revenue: float,
        base_cost: float,
        n_simulations: int = 5000,
    ) -> MonteCarloResult:
        """仅运行蒙特卡洛模拟"""
        return self.mc_simulator.simulate(base_revenue, base_cost, n_simulations)

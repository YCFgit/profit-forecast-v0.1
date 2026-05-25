"""风险评估主逻辑

综合评估承压分配方案的风险：
  1. 目标可达性
  2. 承压分布均匀度
  3. 利润不确定性（蒙特卡洛）
  4. 保底线覆盖率
  5. 新店特殊风险
  6. 季节性风险
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.allocation.target_allocator import AllocationPlan
from src.profit.profit_calculator import ProfitSummary
from src.risk.pressure_distribution import PressureDistributionAnalyzer
from src.risk.reachability import ReachabilityAssessor, ReachabilityResult
from src.risk.scenario_modeler import MonteCarloResult, MonteCarloSimulator


@dataclass
class RiskFactor:
    """风险因素"""
    name: str
    score: float              # 0-100, 越高越危险
    level: str                # low / medium / high / critical
    description: str
    affected_stores: list[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """综合风险评估"""
    overall_score: float          # 综合风险分 0-100
    overall_level: str            # low / medium / high / critical
    factors: list[RiskFactor]     # 各风险因素
    reachability: list[ReachabilityResult] | None = None
    monte_carlo: MonteCarloResult | None = None
    high_risk_stores: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for f in self.factors:
            rows.append({
                "风险因素": f.name,
                "风险分数": round(f.score, 1),
                "风险等级": f.level,
                "说明": f.description,
                "影响门店数": len(f.affected_stores),
            })
        return pd.DataFrame(rows)


class RiskAssessor:
    """风险评估器

    使用方式：
        assessor = RiskAssessor()
        assessment = assessor.assess(
            plan=allocation_plan,
            profit_summary=profit_summary,
            historical_monthly=monthly_data,
        )
    """

    def __init__(self):
        self.reachability_assessor = ReachabilityAssessor()
        self.pressure_analyzer = PressureDistributionAnalyzer()
        self.mc_simulator = MonteCarloSimulator()

    def assess(
        self,
        plan: AllocationPlan,
        profit_summary: ProfitSummary | None = None,
        historical_monthly: dict[str, list[float]] | None = None,
    ) -> RiskAssessment:
        """综合风险评估

        Args:
            plan: 承压分配方案
            profit_summary: 利润测算结果
            historical_monthly: 历史月度数据

        Returns:
            RiskAssessment
        """
        factors = []
        high_risk_stores = set()
        recommendations = []

        # 1. 目标可达性
        targets = {c: a.target for c, a in plan.allocations.items()}
        baselines = {c: a.baseline for c, a in plan.allocations.items()}
        reachability = self.reachability_assessor.assess(targets, baselines, historical_monthly)

        high_risk_reach = [r for r in reachability if r.risk_level in ("high", "critical")]
        if high_risk_reach:
            high_risk_stores.update(r.store_code for r in high_risk_reach)
            factors.append(RiskFactor(
                name="目标可达性",
                score=max(r.risk_score for r in reachability),
                level="high" if len(high_risk_reach) > len(reachability) * 0.2 else "medium",
                description=f"{len(high_risk_reach)}/{len(reachability)} 家门店目标过高",
                affected_stores=[r.store_code for r in high_risk_reach],
            ))
            recommendations.append(
                f"建议降低 {len(high_risk_reach)} 家高风险门店的目标值"
            )
        else:
            factors.append(RiskFactor(
                name="目标可达性",
                score=20,
                level="low",
                description="所有门店目标在合理范围内",
            ))

        # 2. 承压分布
        pressure = self.pressure_analyzer.analyze(plan)
        pressure_score = min(100, pressure.std_pressure_rate * 200)
        pressure_level = "low" if pressure_score < 30 else "medium" if pressure_score < 60 else "high"
        factors.append(RiskFactor(
            name="承压均匀度",
            score=pressure_score,
            level=pressure_level,
            description=f"承压率标准差 {pressure.std_pressure_rate:.1%}, "
                        f"IQR=[{pressure.p25:.1%}, {pressure.p75:.1%}]",
            affected_stores=pressure.outliers,
        ))
        if pressure.outliers:
            recommendations.append(f"关注 {len(pressure.outliers)} 家承压异常门店")

        # 3. 保底线覆盖率
        floor_stores = []
        for code, alloc in plan.allocations.items():
            if alloc.baseline > 0 and alloc.target < alloc.baseline * 0.8:
                floor_stores.append(code)
        floor_score = len(floor_stores) / len(plan.allocations) * 100 if plan.allocations else 0
        factors.append(RiskFactor(
            name="保底线覆盖率",
            score=floor_score,
            level="low" if floor_score == 0 else "high",
            description=f"{len(floor_stores)} 家门店低于保底线",
            affected_stores=floor_stores,
        ))

        # 4. 新店风险
        new_stores = [c for c, a in plan.allocations.items() if a.is_new_store]
        new_risk_score = len(new_stores) / len(plan.allocations) * 50 if plan.allocations else 0
        factors.append(RiskFactor(
            name="新店风险",
            score=new_risk_score,
            level="low" if new_risk_score < 15 else "medium",
            description=f"{len(new_stores)} 家新店需特别关注",
            affected_stores=new_stores,
        ))

        # 5. 利润不确定性（蒙特卡洛）
        mc_result = None
        if profit_summary:
            mc_result = self.mc_simulator.simulate(
                base_revenue=profit_summary.total_revenue,
                base_cost=profit_summary.total_cogs + profit_summary.total_operating_expense,
                n_simulations=5000,
            )
            loss_prob_score = mc_result.loss_probability * 100
            factors.append(RiskFactor(
                name="利润不确定性",
                score=loss_prob_score,
                level="low" if loss_prob_score < 10 else "medium" if loss_prob_score < 30 else "high",
                description=f"亏损概率 {mc_result.loss_probability:.1%}, "
                            f"VaR95={mc_result.var_95:,.0f}",
            ))
            if mc_result.loss_probability > 0.1:
                recommendations.append(
                    f"亏损概率 {mc_result.loss_probability:.1%}，建议预留风险准备金"
                )

        # 综合评分
        if factors:
            overall = sum(f.score for f in factors) / len(factors)
        else:
            overall = 0

        if overall < 30:
            overall_level = "low"
        elif overall < 50:
            overall_level = "medium"
        elif overall < 70:
            overall_level = "high"
        else:
            overall_level = "critical"

        assessment = RiskAssessment(
            overall_score=overall,
            overall_level=overall_level,
            factors=factors,
            reachability=reachability,
            monte_carlo=mc_result,
            high_risk_stores=list(high_risk_stores),
            recommendations=recommendations,
        )

        logger.info(
            f"风险评估完成: 综合分={overall:.1f}, 等级={overall_level}, "
            f"高风险门店={len(high_risk_stores)}, 建议={len(recommendations)} 条"
        )

        return assessment

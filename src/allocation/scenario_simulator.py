"""情景模拟器

模拟不同总目标下的分配方案，帮助老板决策：
  - 保守方案: 总目标 = 基线总额 × 1.10 (增长 10%)
  - 稳健方案: 总目标 = 基线总额 × 1.20 (增长 20%)
  - 激进方案: 总目标 = 基线总额 × 1.30 (增长 30%)
  - 自定义方案: 用户指定总目标
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.allocation.fairness_checker import FairnessChecker, FairnessResult
from src.allocation.target_allocator import AllocationPlan, TargetAllocator
from src.allocation.weight_calculator import StoreProfile


@dataclass
class ScenarioResult:
    """单个情景结果"""
    name: str
    growth_target: float          # 总增长率
    total_target: float           # 总目标
    plan: AllocationPlan          # 分配方案
    fairness: FairnessResult      # 公平性评估


@dataclass
class ScenarioComparison:
    """情景对比"""
    baseline_total: float
    scenarios: dict[str, ScenarioResult]

    def to_dataframe(self) -> pd.DataFrame:
        """转为对比表"""
        rows = []
        for name, scenario in self.scenarios.items():
            rows.append({
                "方案": name,
                "总目标": f"{scenario.total_target:,.0f}",
                "增长率": f"{scenario.growth_target:.0%}",
                "平均承压率": f"{scenario.fairness.avg_pressure_rate:.1%}",
                "承压均匀度": f"{scenario.fairness.cv:.2%}",
                "公平性等级": scenario.fairness.grade,
                "高承压门店": scenario.fairness.extreme_high_count,
                "问题数": len(scenario.fairness.issues),
            })
        return pd.DataFrame(rows)

    def recommend(self) -> str:
        """推荐方案"""
        # 选公平性最好的，且增长率最高的
        best = None
        for name, scenario in self.scenarios.items():
            if scenario.fairness.is_fair:
                if best is None or scenario.growth_target > best[1].growth_target:
                    best = (name, scenario)
        if best:
            return best[0]
        # 如果都不公平，选 CV 最小的
        return min(
            self.scenarios,
            key=lambda n: self.scenarios[n].fairness.cv,
        )


class ScenarioSimulator:
    """情景模拟器

    使用方式：
        simulator = ScenarioSimulator()
        comparison = simulator.simulate(
            baselines={"ST0001": 100_000, ...},
            store_profiles={"ST0001": StoreProfile(...), ...},
        )
        print(comparison.to_dataframe())
        print(f"推荐方案: {comparison.recommend()}")
    """

    def __init__(
        self,
        allocator: TargetAllocator | None = None,
        fairness_checker: FairnessChecker | None = None,
    ):
        self.allocator = allocator or TargetAllocator()
        self.fairness_checker = fairness_checker or FairnessChecker()

    def simulate(
        self,
        baselines: dict[str, float],
        store_profiles: dict[str, StoreProfile] | None = None,
        scenarios: dict[str, float] | None = None,
    ) -> ScenarioComparison:
        """运行多情景模拟

        Args:
            baselines: {门店编码: 基线利润}
            store_profiles: {门店编码: 门店画像}
            scenarios: {方案名: 总增长率}，默认保守/稳健/激进

        Returns:
            ScenarioComparison
        """
        if scenarios is None:
            scenarios = {
                "保守方案": 0.10,
                "稳健方案": 0.20,
                "激进方案": 0.30,
            }

        total_baseline = sum(baselines.values())
        results = {}

        for name, growth in scenarios.items():
            total_target = total_baseline * (1 + growth)

            plan = self.allocator.allocate(
                total_target=total_target,
                baselines=baselines,
                store_profiles=store_profiles,
            )

            fairness = self.fairness_checker.check(plan)

            results[name] = ScenarioResult(
                name=name,
                growth_target=growth,
                total_target=total_target,
                plan=plan,
                fairness=fairness,
            )

            logger.info(
                f"情景 [{name}]: 目标={total_target:,.0f} (+{growth:.0%}), "
                f"公平性={fairness.grade}"
            )

        comparison = ScenarioComparison(
            baseline_total=total_baseline,
            scenarios=results,
        )

        recommended = comparison.recommend()
        logger.info(f"推荐方案: {recommended}")

        return comparison

    def simulate_custom(
        self,
        total_target: float,
        baselines: dict[str, float],
        store_profiles: dict[str, StoreProfile] | None = None,
    ) -> ScenarioResult:
        """自定义目标模拟"""
        plan = self.allocator.allocate(total_target, baselines, store_profiles)
        fairness = self.fairness_checker.check(plan)

        return ScenarioResult(
            name="自定义方案",
            growth_target=(total_target - sum(baselines.values())) / sum(baselines.values()),
            total_target=total_target,
            plan=plan,
            fairness=fairness,
        )

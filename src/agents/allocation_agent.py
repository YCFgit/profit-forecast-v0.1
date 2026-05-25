"""承压分配 Agent

负责将老板总目标分配到各门店。
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.allocation.target_allocator import TargetAllocator, AllocationPlan
from src.allocation.weight_calculator import StoreProfile, WeightCalculator
from src.allocation.fairness_checker import FairnessChecker, FairnessResult
from src.allocation.scenario_simulator import ScenarioSimulator, ScenarioComparison


@dataclass
class AllocationResult:
    """分配结果"""
    plan: AllocationPlan
    fairness: FairnessResult
    scenario_comparison: ScenarioComparison | None = None
    store_count: int = 0


class AllocationAgent:
    """承压分配 Agent

    使用方式：
        agent = AllocationAgent()
        result = agent.allocate(total_target, baselines, store_profiles)
    """

    def __init__(self):
        self.allocator = TargetAllocator()
        self.weight_calculator = WeightCalculator()
        self.fairness_checker = FairnessChecker()
        self.scenario_simulator = ScenarioSimulator()

    def allocate(
        self,
        total_target: float,
        baselines: dict[str, float],
        store_profiles: dict[str, StoreProfile],
        with_scenarios: bool = True,
    ) -> AllocationResult:
        """执行承压分配

        Args:
            total_target: 老板设定的总目标
            baselines: {门店编码: 基线利润}
            store_profiles: {门店编码: 门店画像}
            with_scenarios: 是否同时生成情景对比

        Returns:
            AllocationResult
        """
        # 执行分配
        plan = self.allocator.allocate(total_target, baselines, store_profiles)

        # 公平性检查
        fairness = self.fairness_checker.check(plan)

        # 情景模拟
        scenario_comparison = None
        if with_scenarios:
            scenario_comparison = self.scenario_simulator.simulate(baselines, store_profiles)

        result = AllocationResult(
            plan=plan,
            fairness=fairness,
            scenario_comparison=scenario_comparison,
            store_count=plan.store_count,
        )

        logger.info(
            f"承压分配完成: {result.store_count} 家门店, "
            f"总目标={plan.total_target:,.0f}, "
            f"公平性={fairness.grade}"
        )

        return result

    def build_store_profiles(
        self,
        stores_df: pd.DataFrame,
        metrics_df: pd.DataFrame,
    ) -> dict[str, StoreProfile]:
        """从数据构建门店画像

        Args:
            stores_df: 门店数据
            metrics_df: 月度指标数据

        Returns:
            {门店编码: StoreProfile}
        """
        profiles = {}

        for _, row in stores_df.iterrows():
            code = row["store_code"]
            store_metrics = metrics_df[metrics_df["store_code"] == code]

            avg_profit = store_metrics["gross_profit"].mean() if "gross_profit" in store_metrics.columns else 0
            avg_sqm = store_metrics["sales_per_sqm"].mean() if "sales_per_sqm" in store_metrics.columns else 0
            tier = row.get("commercial_tier", "C")

            # 计算增长率
            if len(store_metrics) >= 6:
                recent = store_metrics.tail(3)["sales_amount"].mean()
                prev = store_metrics.head(3)["sales_amount"].mean()
                growth = (recent - prev) / prev if prev > 0 else 0
            else:
                growth = 0

            # 计算开业月数
            opening_date = row.get("opening_date")
            if opening_date:
                from datetime import date
                if isinstance(opening_date, str):
                    opening_date = date.fromisoformat(opening_date)
                opening_months = (date.today() - opening_date).days // 30
            else:
                opening_months = 365  # 默认

            profiles[code] = StoreProfile(
                store_code=code,
                historical_profit=avg_profit,
                sales_per_sqm=avg_sqm,
                commercial_tier=tier,
                city_level=row.get("city_level", "二线"),
                store_area=row.get("store_area", 100),
                growth_rate=growth,
                opening_months=opening_months,
                baseline_sales=store_metrics["sales_amount"].mean() if "sales_amount" in store_metrics.columns else 0,
            )

        logger.info(f"构建门店画像: {len(profiles)} 家")
        return profiles

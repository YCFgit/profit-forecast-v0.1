"""承压分配 Agent

负责将老板总目标分配到各门店。
支持两种分配模式：
- MIP 运筹优化（推荐）：最大化期望变动边际利润
- 权重评分分配（降级）：按权重比例分配
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.allocation.target_allocator import TargetAllocator, AllocationPlan
from src.allocation.weight_calculator import StoreProfile, WeightCalculator
from src.allocation.fairness_checker import FairnessChecker, FairnessResult
from src.allocation.scenario_simulator import ScenarioSimulator, ScenarioComparison
from src.allocation.mip_allocator import MIPAllocator, MIPAllocationResult


@dataclass
class AllocationResult:
    """分配结果"""
    plan: AllocationPlan | None = None
    mip_result: MIPAllocationResult | None = None
    fairness: FairnessResult | None = None
    scenario_comparison: ScenarioComparison | None = None
    store_count: int = 0
    method: str = "weight"  # "mip" | "weight"


class AllocationAgent:
    """承压分配 Agent

    使用方式：
        agent = AllocationAgent()
        result = agent.allocate(total_target, baselines, store_profiles)
        result = agent.allocate_mip(total_target, baselines, marginal_rates, ceilings, store_meta)
    """

    def __init__(self):
        self.allocator = TargetAllocator()
        self.mip_allocator = MIPAllocator()
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

    def allocate_mip(
        self,
        total_target: float,
        baselines: dict[str, float],
        cost_structures: dict[str, dict[str, float]] | None = None,
        store_meta: dict[str, dict] | None = None,
        exclude_stores: set[str] | None = None,
        seasonal_indices: dict[str, float] | None = None,
        p75_sales: dict[str, float] | None = None,
    ) -> AllocationResult:
        """执行 MIP 运筹优化承压分配

        最大化期望变动边际利润，考虑难度档位达成概率。

        Args:
            total_target: 老板设定的总目标
            baselines: {门店编码: 基线收入}
            cost_structures: {门店编码: 成本明细}，用于计算变动边际利润率
            store_meta: {门店编码: {"region": ..., "brand": ...}}
            exclude_stores: 不参与分配的门店集合
            seasonal_indices: {门店编码: 季节指数}，用于天花板计算
            p75_sales: {门店编码: P75销售额}，用于天花板计算

        Returns:
            AllocationResult（method="mip"）
        """
        # 计算变动边际利润率
        marginal_rates = self._compute_marginal_rates(baselines, cost_structures)

        # 计算天花板（P75 × 季节指数，或基线 × 1.5）
        ceilings = self._compute_ceilings(baselines, seasonal_indices, p75_sales)

        # 执行 MIP 分配
        mip_result = self.mip_allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=marginal_rates,
            ceilings=ceilings,
            store_meta=store_meta,
            exclude_stores=exclude_stores,
        )

        result = AllocationResult(
            mip_result=mip_result,
            store_count=mip_result.store_count,
            method="mip",
        )

        logger.info(
            f"MIP承压分配完成: {mip_result.participating_count} 家门店参与, "
            f"总目标={total_target:,.0f}, "
            f"分配总额={mip_result.total_allocated:,.0f}, "
            f"期望边际利润={mip_result.expected_total_marginal_profit:,.0f}"
        )

        return result

    def _compute_marginal_rates(
        self,
        baselines: dict[str, float],
        cost_structures: dict[str, dict[str, float]] | None,
    ) -> dict[str, float]:
        """计算变动边际利润率

        变动边际利润率 = 1 - COGS率 - 税金率 - 商场扣点率 - 附加税率
        即每增加1元收入，变动边际利润增加多少。
        """
        rates = {}
        for code, baseline in baselines.items():
            if baseline <= 0:
                rates[code] = 0.10
                continue

            costs = (cost_structures or {}).get(code, {})
            cogs_ratio = costs.get("cogs_ratio", 0.45)
            # 变动费用率：商场扣点 + 附加税 + 其他变动
            mall_fee_ratio = costs.get("mall_fee_ratio", 0.03)
            tax_surcharge_ratio = costs.get("tax_surcharge_ratio", 0.01)
            variable_other_ratio = costs.get("variable_other_ratio", 0.02)

            # 变动边际利润率 = 1 - 全部变动成本率
            m_var = 1.0 - cogs_ratio - mall_fee_ratio - tax_surcharge_ratio - variable_other_ratio
            # 限制在合理范围 [0.05, 0.60]
            m_var = max(0.05, min(0.60, m_var))
            rates[code] = round(m_var, 4)

        return rates

    def _compute_ceilings(
        self,
        baselines: dict[str, float],
        seasonal_indices: dict[str, float] | None,
        p75_sales: dict[str, float] | None,
    ) -> dict[str, float]:
        """计算门店天花板

        天花板 = P75 × 阻尼季节指数
        降级：基线 × 1.5
        """
        ceilings = {}
        for code, baseline in baselines.items():
            if baseline <= 0:
                ceilings[code] = 0
                continue

            if p75_sales and code in p75_sales:
                p75 = p75_sales[code]
                si = (seasonal_indices or {}).get(code, 1.0)
                # 阻尼季节指数：1 + (raw - 1) × 0.50
                damped_si = 1.0 + (si - 1.0) * 0.50
                ceilings[code] = round(p75 * damped_si, 0)
            else:
                ceilings[code] = round(baseline * 1.5, 0)

        return ceilings

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
        import math
        profiles = {}

        for _, row in stores_df.iterrows():
            code = row["store_code"]
            store_metrics = metrics_df[metrics_df["store_code"] == code]

            if store_metrics.empty:
                continue

            avg_profit = store_metrics["gross_profit"].mean() if "gross_profit" in store_metrics.columns else 0
            avg_sqm = store_metrics["sales_per_sqm"].mean() if "sales_per_sqm" in store_metrics.columns else 0
            tier = row.get("commercial_tier", "C")
            if not tier or (isinstance(tier, float) and math.isnan(tier)):
                tier = "C"

            # 计算增长率
            if len(store_metrics) >= 6:
                recent = store_metrics.tail(3)["sales_amount"].mean()
                prev = store_metrics.head(3)["sales_amount"].mean()
                growth = (recent - prev) / prev if prev > 0 else 0
            else:
                growth = 0

            # 处理 NaN 值
            if math.isnan(avg_profit) if isinstance(avg_profit, float) else False:
                avg_profit = 0.0
            if math.isnan(growth) if isinstance(growth, float) else False:
                growth = 0.0

            # 计算开业月数
            opening_date = row.get("opening_date")
            if opening_date:
                from datetime import date
                if isinstance(opening_date, str):
                    opening_date = date.fromisoformat(opening_date)
                opening_months = (date.today() - opening_date).days // 30
            else:
                opening_months = 365  # 默认

            store_area = row.get("store_area", 100)
            if store_area is None or (isinstance(store_area, float) and math.isnan(store_area)):
                store_area = 100.0

            baseline_sales = store_metrics["sales_amount"].mean() if "sales_amount" in store_metrics.columns else 0
            if isinstance(baseline_sales, float) and math.isnan(baseline_sales):
                baseline_sales = 0.0

            profiles[code] = StoreProfile(
                store_code=code,
                historical_profit=avg_profit if not (isinstance(avg_profit, float) and math.isnan(avg_profit)) else 0.0,
                sales_per_sqm=avg_sqm if not (isinstance(avg_sqm, float) and math.isnan(avg_sqm)) else 0.0,
                commercial_tier=tier,
                city_level=row.get("city_level", "二线") or "二线",
                store_area=store_area,
                growth_rate=growth,
                opening_months=opening_months,
                baseline_sales=baseline_sales,
            )

        logger.info(f"构建门店画像: {len(profiles)} 家")
        return profiles

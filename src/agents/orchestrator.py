"""项目统筹 Agent（调度中心）

协调各专业 Agent 完成完整的利润测算流程：
  数据采集 → 基线预估 → 承压分配 → 利润测算 → 风险评估
"""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from loguru import logger

from src.agents.data_agent import DataAgent, DataCollectionResult
from src.agents.baseline_agent import BaselineAgent, BaselineResult
from src.agents.allocation_agent import AllocationAgent, AllocationResult
from src.agents.profit_agent import ProfitAgent, ProfitResult
from src.agents.risk_agent import RiskResult, RiskAgent
from src.allocation.weight_calculator import StoreProfile
from src.profit.cost_estimator import CostEstimator


@dataclass
class PipelineResult:
    """完整流程结果"""
    # 各阶段结果
    data: DataCollectionResult
    baseline: BaselineResult
    allocation: AllocationResult
    profit: ProfitResult
    risk: RiskResult

    # 元信息
    total_target: float
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float = 0
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> dict:
        """生成汇总摘要"""
        return {
            "总目标": self.total_target,
            "门店数": self.allocation.store_count,
            "分配总额": self.allocation.plan.total_allocated,
            "平均增长率": f"{self.allocation.plan.avg_growth_rate:.1%}",
            "公平性等级": self.allocation.fairness.grade,
            "总收入": self.profit.summary.total_revenue,
            "净利润": self.profit.summary.total_net_profit,
            "净利率": f"{self.profit.summary.avg_net_margin:.1%}",
            "盈利门店": self.profit.summary.profitable_count,
            "亏损门店": self.profit.summary.loss_count,
            "风险等级": self.risk.assessment.overall_level,
            "风险分": self.risk.assessment.overall_score,
            "高风险门店": len(self.risk.assessment.high_risk_stores),
            "建议数": len(self.risk.recommendations),
            "耗时(秒)": round(self.duration_seconds, 1),
        }


class Orchestrator:
    """项目统筹 Agent

    使用方式：
        orchestrator = Orchestrator()
        result = await orchestrator.run(total_target=10_000_000)
    """

    def __init__(self, adapter: str | None = None):
        self.data_agent = DataAgent(adapter)
        self.baseline_agent = BaselineAgent()
        self.allocation_agent = AllocationAgent()
        self.profit_agent = ProfitAgent()
        self.risk_agent = RiskAgent()

    async def run(
        self,
        total_target: float,
        adapter: str | None = None,
        with_scenarios: bool = True,
    ) -> PipelineResult:
        """执行完整流程

        Args:
            total_target: 老板设定的总利润目标
            adapter: 数据源适配器，None 则使用配置
            with_scenarios: 是否生成情景对比

        Returns:
            PipelineResult
        """
        started_at = datetime.now()
        errors = []

        if adapter:
            self.data_agent = DataAgent(adapter)

        # ============================================================
        # Phase 1: 数据采集
        # ============================================================
        logger.info("=" * 50)
        logger.info("Phase 1: 数据采集")
        logger.info("=" * 50)

        try:
            data = await self.data_agent.collect()
        except Exception as e:
            logger.error(f"数据采集失败: {e}")
            errors.append(f"数据采集: {e}")
            raise

        # ============================================================
        # Phase 2: 基线预估
        # ============================================================
        logger.info("=" * 50)
        logger.info("Phase 2: 基线预估")
        logger.info("=" * 50)

        try:
            baseline = self.baseline_agent.forecast(
                monthly_metrics=data.monthly_metrics,
                stores_df=data.stores,
                daily_sales=data.daily_sales,
                switch_status=data.switch_status if hasattr(data, 'switch_status') else None,
            )
        except Exception as e:
            logger.error(f"基线预估失败: {e}")
            errors.append(f"基线预估: {e}")
            raise

        # ============================================================
        # Phase 3: 承压分配
        # ============================================================
        logger.info("=" * 50)
        logger.info("Phase 3: 承压分配")
        logger.info("=" * 50)

        try:
            store_profiles = self.allocation_agent.build_store_profiles(
                data.stores, data.monthly_metrics
            )
            allocation = self.allocation_agent.allocate(
                total_target=total_target,
                baselines=baseline.baselines,
                store_profiles=store_profiles,
                with_scenarios=with_scenarios,
            )
        except Exception as e:
            logger.error(f"承压分配失败: {e}")
            errors.append(f"承压分配: {e}")
            raise

        # ============================================================
        # Phase 4: 利润测算
        # ============================================================
        logger.info("=" * 50)
        logger.info("Phase 4: 利润测算")
        logger.info("=" * 50)

        try:
            targets = {c: a.target for c, a in allocation.plan.allocations.items()}

            # 构建区域和类型映射
            store_region_map = {}
            store_type_map = {}
            for _, row in data.stores.iterrows():
                store_region_map[row["store_code"]] = row.get("region", "未知")
                store_type_map[row["store_code"]] = row.get("store_type", "标准店")

            # 从真实损益数据构建成本结构
            cost_structures = None
            if not data.store_loss.empty:
                cost_estimator = CostEstimator()
                cost_structures = cost_estimator.from_store_loss_data(
                    store_loss_df=data.store_loss,
                    targets=targets,
                    months=3,
                )

            profit = self.profit_agent.calculate(
                targets=targets,
                baselines=baseline.baselines,
                cost_structures=cost_structures,
                store_region_map=store_region_map,
                store_type_map=store_type_map,
            )
        except Exception as e:
            logger.error(f"利润测算失败: {e}")
            errors.append(f"利润测算: {e}")
            raise

        # ============================================================
        # Phase 5: 风险评估
        # ============================================================
        logger.info("=" * 50)
        logger.info("Phase 5: 风险评估")
        logger.info("=" * 50)

        try:
            # 构建历史月度数据
            historical_monthly = {}
            for code in baseline.baselines:
                store_sales = data.daily_sales[
                    data.daily_sales["store_code"] == code
                ] if not data.daily_sales.empty else pd.DataFrame()
                if not store_sales.empty and "sales_amount" in store_sales.columns:
                    historical_monthly[code] = store_sales["sales_amount"].tolist()

            risk = self.risk_agent.assess(
                plan=allocation.plan,
                profit_summary=profit.summary,
                historical_monthly=historical_monthly,
            )
        except Exception as e:
            logger.error(f"风险评估失败: {e}")
            errors.append(f"风险评估: {e}")
            raise

        # ============================================================
        # 汇总
        # ============================================================
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()

        result = PipelineResult(
            data=data,
            baseline=baseline,
            allocation=allocation,
            profit=profit,
            risk=risk,
            total_target=total_target,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            errors=errors,
        )

        logger.info(f"完整流程执行完成: 耗时 {duration:.1f} 秒")
        for k, v in result.summary.items():
            logger.info(f"  {k}: {v}")

        return result

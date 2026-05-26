"""编排器

职责：协调各 Agent 执行完整的利润测算流程。
"""

from loguru import logger

from src.agents.data_agent import DataAgent
from src.agents.baseline_agent import BaselineAgent
from src.agents.profit_agent import ProfitAgent
from src.agents.risk_agent import RiskAgent
from src.agents.allocation_agent import AllocationAgent
from src.allocation.weight_calculator import StoreProfile


class Orchestrator:
    """编排器"""

    def __init__(self, adapter: str = "mock"):
        self.name = "Orchestrator"
        self.data_agent = DataAgent(adapter=adapter)
        self.baseline_agent = BaselineAgent()
        self.profit_agent = ProfitAgent()
        self.risk_agent = RiskAgent()
        self.allocation_agent = AllocationAgent()

    def run(
        self,
        store_no: str = None,
        date_range: tuple = None,
        perspective: str = "actual",
        boss_target: float = None,
    ) -> dict:
        """执行完整利润测算流程

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_date, end_date)
            perspective: "actual" | "rebate"
            boss_target: 老板总目标（可选，用于承压分配）

        Returns:
            {sales_df, baselines, profit_summary, risk_result, allocation_result}
        """
        logger.info(f"[{self.name}] 开始执行流程: perspective={perspective}")

        # Step 1: 数据采集
        sales_df = self.data_agent.collect(
            store_no=store_no,
            date_range=date_range,
            perspective=perspective,
        )
        if sales_df.empty:
            logger.warning(f"[{self.name}] 数据为空，终止流程")
            return {"sales_df": sales_df, "baselines": {}, "profit_summary": None, "risk_result": None}

        # Step 2: 基线预估
        baselines = self.baseline_agent.estimate(sales_df)

        # Step 3: 利润测算
        profit_summary = self.profit_agent.calculate(sales_df)

        # Step 4: 风险评估
        risk_result = self.risk_agent.assess(sales_df)

        # Step 5: 承压分配（可选）
        allocation_result = None
        if boss_target and baselines.get("store_baselines"):
            try:
                # 从基线数据构建默认门店画像
                store_profiles = self._build_default_profiles(baselines["store_baselines"])
                allocation_result = self.allocation_agent.allocate(
                    total_target=boss_target,
                    baselines=baselines["store_baselines"],
                    store_profiles=store_profiles,
                )
            except Exception as e:
                logger.warning(f"[{self.name}] 承压分配失败: {e}")

        logger.info(
            f"[{self.name}] 流程完成: "
            f"门店={len(sales_df['store_no'].unique())}, "
            f"总收入={profit_summary.total_revenue:,.0f}, "
            f"高风险={risk_result['summary'].get('high_risk', 0) + risk_result['summary'].get('critical_risk', 0)}"
        )

        return {
            "sales_df": sales_df,
            "baselines": baselines,
            "profit_summary": profit_summary,
            "risk_result": risk_result,
            "allocation_result": allocation_result,
        }

    @staticmethod
    def _build_default_profiles(store_baselines: dict[str, float]) -> dict[str, StoreProfile]:
        """从基线数据构建默认门店画像

        Args:
            store_baselines: {store_no: baseline_revenue}

        Returns:
            {store_no: StoreProfile}
        """
        profiles = {}
        for store_no, baseline in store_baselines.items():
            profiles[store_no] = StoreProfile(
                store_code=store_no,
                historical_profit=baseline * 0.15,  # 默认利润率 15%
                sales_per_sqm=0,
                commercial_tier="C",
                city_level="二线",
                store_area=100,
                growth_rate=0,
                opening_months=365,
                baseline_sales=baseline,
            )
        return profiles

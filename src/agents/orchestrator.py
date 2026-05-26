"""编排器

职责：协调各 Agent 执行完整的利润测算流程。

adapter 选项：
    - "mock": 使用 MockDataCollector（开发/测试）
    - "starrocks": 使用 SalesDataCollector 连接 StarRocks
    - "etl": 使用 ETLDataAgent（ETL Pipeline，真实数据源）
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
        self.adapter = adapter

        if adapter == "etl":
            from src.agents.etl_data_agent import ETLDataAgent
            self.data_agent = ETLDataAgent()
        else:
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

    def run_etl(
        self,
        date_range: tuple[str, str],
        perspective: str = "actual",
        store_no: str = None,
        write_mysql: bool = True,
        write_csv: bool = True,
        boss_target: float = None,
    ) -> dict:
        """ETL + 利润测算一体化流程

        先从 StarRocks 提取数据写入本地 MySQL/CSV，再执行利润测算。

        Args:
            date_range: (start_date, end_date)
            perspective: "actual" | "rebate"
            store_no: 指定门店（可选）
            write_mysql: 是否写入本地 MySQL
            write_csv: 是否输出 CSV
            boss_target: 老板总目标（可选）

        Returns:
            {etl_result, profit_result}
        """
        from src.data.etl.pipeline import ETLPipeline

        logger.info(f"[{self.name}] ETL + 利润测算: range={date_range}, perspective={perspective}")

        # Step 1: ETL 提取
        etl = ETLPipeline(write_mysql=write_mysql, write_csv=write_csv)
        etl_result = etl.run_full(date_range, perspective, store_no)

        # Step 2: 用 ETL 加载的数据跑利润测算
        # 重新设置 adapter 为 etl，使用 SalesLoader 的数据
        etl_agent = ETLDataAgent() if self.adapter != "etl" else self.data_agent
        sales_df = etl_agent.collect(store_no=store_no, date_range=date_range, perspective=perspective)

        if sales_df.empty:
            logger.warning(f"[{self.name}] ETL 数据为空，跳过利润测算")
            return {"etl_result": etl_result, "profit_result": None}

        # 复用 run() 的后续逻辑
        baselines = self.baseline_agent.estimate(sales_df)
        profit_summary = self.profit_agent.calculate(sales_df)
        risk_result = self.risk_agent.assess(sales_df)

        allocation_result = None
        if boss_target and baselines.get("store_baselines"):
            try:
                store_profiles = self._build_default_profiles(baselines["store_baselines"])
                allocation_result = self.allocation_agent.allocate(
                    total_target=boss_target,
                    baselines=baselines["store_baselines"],
                    store_profiles=store_profiles,
                )
            except Exception as e:
                logger.warning(f"[{self.name}] 承压分配失败: {e}")

        return {
            "etl_result": etl_result,
            "profit_result": {
                "sales_df": sales_df,
                "baselines": baselines,
                "profit_summary": profit_summary,
                "risk_result": risk_result,
                "allocation_result": allocation_result,
            },
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

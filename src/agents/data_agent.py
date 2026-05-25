"""数据采集 Agent

负责从数据源采集门店、销售、月度指标等数据。
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.data.collectors.factory import create_collector
from src.data.validators.quality_checker import run_quality_check


@dataclass
class DataCollectionResult:
    """数据采集结果"""
    stores: pd.DataFrame
    daily_sales: pd.DataFrame
    monthly_metrics: pd.DataFrame
    daily_target_cost: pd.DataFrame = field(default_factory=pd.DataFrame)
    switch_status: pd.DataFrame = field(default_factory=pd.DataFrame)
    store_loss: pd.DataFrame = field(default_factory=pd.DataFrame)
    cost_structure: pd.DataFrame = field(default_factory=pd.DataFrame)
    quality_errors: list[str] = field(default_factory=list)
    store_count: int = 0
    sales_count: int = 0
    metrics_count: int = 0


class DataAgent:
    """数据采集 Agent

    使用方式：
        agent = DataAgent()
        result = await agent.collect()
    """

    def __init__(self, adapter: str | None = None):
        self.adapter = adapter

    async def collect(self) -> DataCollectionResult:
        """采集全量数据"""
        collector = create_collector(self.adapter)
        quality_errors = []

        async with collector:
            # 采集门店数据
            stores = await collector.fetch_stores()
            quality = run_quality_check(
                stores, name="门店数据",
                critical_cols=["store_code", "store_name"],
                duplicate_subset=["store_code"],
            )
            quality_errors.extend(quality.errors)

            # 采集日销数据
            daily_sales = await collector.fetch_daily_sales()
            if not daily_sales.empty:
                quality = run_quality_check(
                    daily_sales, name="日销数据",
                    critical_cols=["store_code", "sale_date", "sales_amount"],
                )
                quality_errors.extend(quality.errors)

            # 采集月度指标
            monthly_metrics = await collector.fetch_monthly_metrics()
            if not monthly_metrics.empty:
                quality = run_quality_check(
                    monthly_metrics, name="月度指标",
                    critical_cols=["store_code", "year_month"],
                )
                quality_errors.extend(quality.errors)

            # 采集日店铺基础目标（可选）
            daily_target_cost = await collector.fetch_daily_target_cost()

            # 采集开关状态矩阵（可选）
            switch_status = await collector.fetch_switch_status()

            # 采集门店日损益数据（用于利润测算的真实成本结构）
            store_loss = await collector.fetch_store_loss()
            if not store_loss.empty:
                quality = run_quality_check(
                    store_loss, name="门店损益数据",
                    critical_cols=["store_code", "sale_date"],
                )
                quality_errors.extend(quality.errors)

            # 采集成本结构数据（备用）
            cost_structure = await collector.fetch_cost_structure()

        result = DataCollectionResult(
            stores=stores,
            daily_sales=daily_sales,
            monthly_metrics=monthly_metrics,
            daily_target_cost=daily_target_cost,
            switch_status=switch_status,
            store_loss=store_loss,
            cost_structure=cost_structure,
            quality_errors=quality_errors,
            store_count=len(stores),
            sales_count=len(daily_sales),
            metrics_count=len(monthly_metrics),
        )

        logger.info(
            f"数据采集完成: 门店={result.store_count}, "
            f"日销={result.sales_count}, 月度={result.metrics_count}, "
            f"损益={len(store_loss)}, 成本={len(cost_structure)}, "
            f"质量问题={len(quality_errors)}"
        )

        return result

    async def collect_stores(self) -> pd.DataFrame:
        """仅采集门店数据"""
        collector = create_collector(self.adapter)
        async with collector:
            return await collector.fetch_stores()

    async def collect_sales(self, store_codes: list[str] | None = None) -> pd.DataFrame:
        """采集日销数据，可按门店筛选"""
        collector = create_collector(self.adapter)
        async with collector:
            df = await collector.fetch_daily_sales()
            if store_codes:
                df = df[df["store_code"].isin(store_codes)]
            return df

    async def collect_monthly_metrics(self, store_codes: list[str] | None = None) -> pd.DataFrame:
        """采集月度指标，可按门店筛选"""
        collector = create_collector(self.adapter)
        async with collector:
            df = await collector.fetch_monthly_metrics()
            if store_codes:
                df = df[df["store_code"].isin(store_codes)]
            return df

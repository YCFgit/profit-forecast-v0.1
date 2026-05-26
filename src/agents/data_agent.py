"""数据采集 Agent

职责：从 3 张销售表采集数据，生成统一宽表。
"""

import pandas as pd
from loguru import logger

from src.data.collectors.sales_collector import SalesDataCollector


class DataAgent:
    """数据采集 Agent"""

    def __init__(self, adapter: str = "mock"):
        self.collector = SalesDataCollector(adapter=adapter)
        self.name = "DataAgent"

    def collect(
        self,
        store_no: str = None,
        date_range: tuple = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """采集数据并生成统一宽表

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_date, end_date)
            perspective: "actual" | "rebate"

        Returns:
            统一销售宽表 DataFrame
        """
        logger.info(f"[{self.name}] 开始采集数据: store={store_no}, range={date_range}")

        df = self.collector.collect_unified_sales(
            store_no=store_no,
            date_range=date_range,
            perspective=perspective,
        )

        logger.info(f"[{self.name}] 数据采集完成: {len(df)} 行, {df['store_no'].nunique()} 家门店")
        return df

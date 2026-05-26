"""ETL 数据采集 Agent

通过 ETLPipeline 的 SalesLoader 从 StarRocks 读取真实数据，
替代 DataAgent 的 Mock/SalesDataCollector 模式。
"""

import pandas as pd
from loguru import logger

from src.data.etl.loader import SalesLoader


class ETLDataAgent:
    """ETL 数据采集 Agent（真实数据源）"""

    def __init__(self):
        self.loader = SalesLoader()
        self.name = "ETLDataAgent"

    def collect(
        self,
        store_no: str = None,
        date_range: tuple = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """从 StarRocks 采集数据并生成统一宽表

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_date, end_date)
            perspective: "actual" | "rebate"

        Returns:
            统一销售宽表 DataFrame
        """
        logger.info(f"[{self.name}] 从 StarRocks 采集: store={store_no}, range={date_range}")

        df = self.loader.load_unified_sales(
            store_no=store_no,
            date_range=date_range,
            perspective=perspective,
        )

        if not df.empty:
            logger.info(f"[{self.name}] 采集完成: {len(df)} 行, {df['store_no'].nunique()} 家门店")
        else:
            logger.warning(f"[{self.name}] 采集结果为空")

        return df

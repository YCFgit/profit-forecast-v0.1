"""MySQL 数据采集 Agent

从本地 MySQL 数据库读取已加载的真实数据，
替代 MockDataAgent 用于生产环境。
"""

import pandas as pd
from loguru import logger

from src.data.collectors.mysql_collector import MySQLCollector


class MySQLDataAgent:
    """MySQL 数据采集 Agent"""

    def __init__(self):
        self.collector = MySQLCollector()
        self.name = "MySQLDataAgent"

    def collect(
        self,
        store_no: str = None,
        date_range: tuple = None,
        perspective: str = "actual",
    ) -> pd.DataFrame:
        """从 MySQL 采集数据并生成统一宽表

        Args:
            store_no: 门店编码，None 表示全部
            date_range: (start_month, end_month) 格式 YYYY-MM 或 YYYYMM
            perspective: "actual" | "rebate"

        Returns:
            统一销售宽表 DataFrame
        """
        store_codes = [store_no] if store_no else None

        # 解析日期范围
        start_month = None
        end_month = None
        if date_range:
            start_month = str(date_range[0]).replace("-", "")[:6]
            end_month = str(date_range[1]).replace("-", "")[:6]
            # 转为 YYYY-MM 格式
            if len(start_month) == 6:
                start_month = start_month[:4] + "-" + start_month[4:]
            if len(end_month) == 6:
                end_month = end_month[:4] + "-" + end_month[4:]

        logger.info(f"[{self.name}] 从 MySQL 采集: store={store_no}, range={date_range}")

        df = self.collector.collect_unified_sales(
            store_codes=store_codes,
            start_month=start_month,
            end_month=end_month,
        )

        if not df.empty:
            logger.info(f"[{self.name}] 采集完成: {len(df)} 行, {df['store_no'].nunique()} 家门店")
        else:
            logger.warning(f"[{self.name}] 采集结果为空")

        return df

"""ETL 数据加工模块

从 StarRocks 读取真实业务数据，加工后写入本地 MySQL + CSV 宽表。
"""

from src.data.etl.loader import SalesLoader
from src.data.etl.pipeline import ETLPipeline
from src.data.etl.rebate import compare_perspectives, summarize_rebate_impact
from src.data.etl.writer import CSVWriter, MySQLWriter

__all__ = [
    "ETLPipeline", "SalesLoader", "MySQLWriter", "CSVWriter",
    "compare_perspectives", "summarize_rebate_impact",
]

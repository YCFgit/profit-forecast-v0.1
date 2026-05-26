"""ETL Pipeline — 真实数据加工主入口

从 StarRocks 读取 → 加工 → 写入本地 MySQL + CSV 宽表。

使用方式：
    pipeline = ETLPipeline()
    result = pipeline.run_full(date_range=("2026-01-01", "2026-03-31"))
    # result.stores_count, result.sales_rows, result.output_files
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.data.etl.loader import SalesLoader
from src.data.etl.writer import CSVWriter, MySQLWriter


@dataclass
class ETLResult:
    """ETL 执行结果"""
    stores_count: int = 0
    loss_rows: int = 0
    pos_rows: int = 0
    monthly_rows: int = 0
    unified_rows: int = 0
    output_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.stores_count > 0


class ETLPipeline:
    """ETL 加工流水线

    协调 SalesLoader → 加工 → MySQLWriter / CSVWriter 流程。

    Args:
        write_mysql: 是否写入本地 MySQL
        write_csv: 是否输出 CSV 文件
        output_dir: CSV 输出目录
    """

    def __init__(
        self,
        write_mysql: bool = True,
        write_csv: bool = True,
        output_dir: str = "data/etl_output",
    ):
        self.loader = SalesLoader()
        self.mysql_writer = MySQLWriter() if write_mysql else None
        self.csv_writer = CSVWriter(output_dir) if write_csv else None

    def run_full(
        self,
        date_range: tuple[str, str],
        perspective: str = "actual",
        store_no: str | None = None,
    ) -> ETLResult:
        """执行完整 ETL 流程

        Args:
            date_range: (start_date, end_date) 格式 "YYYY-MM-DD"
            perspective: "actual" (业绩口径) 或 "rebate" (返利口径)
            store_no: 指定门店（可选，None=全部）

        Returns:
            ETLResult
        """
        result = ETLResult()
        logger.info(f"[ETL] 开始: date_range={date_range}, perspective={perspective}")

        # 1. 门店主数据
        try:
            stores_df = self.run_stores(store_no)
            result.stores_count = len(stores_df)
        except Exception as e:
            result.errors.append(f"门店数据加载失败: {e}")
            logger.error(f"[ETL] 门店数据加载失败: {e}")

        # 2. 日损益
        try:
            loss_df = self.run_store_loss(date_range, perspective, store_no)
            result.loss_rows = len(loss_df)
        except Exception as e:
            result.errors.append(f"损益数据加载失败: {e}")
            logger.error(f"[ETL] 损益数据加载失败: {e}")

        # 3. POS 订单
        try:
            pos_df = self.run_pos_orders(date_range, store_no)
            result.pos_rows = len(pos_df)
        except Exception as e:
            result.errors.append(f"POS数据加载失败: {e}")
            logger.error(f"[ETL] POS数据加载失败: {e}")

        # 4. 月度指标
        try:
            monthly_df = self.run_monthly_metrics(date_range, store_no)
            result.monthly_rows = len(monthly_df)
        except Exception as e:
            result.errors.append(f"月度指标加载失败: {e}")
            logger.error(f"[ETL] 月度指标加载失败: {e}")

        # 5. 统一销售宽表
        try:
            unified_df = self.loader.load_unified_sales(store_no, date_range, perspective)
            result.unified_rows = len(unified_df)
            if self.csv_writer and not unified_df.empty:
                path = self.csv_writer.write_unified_sales(unified_df)
                if path:
                    result.output_files.append(path)
        except Exception as e:
            result.errors.append(f"统一宽表生成失败: {e}")
            logger.error(f"[ETL] 统一宽表生成失败: {e}")

        logger.info(
            f"[ETL] 完成: 门店={result.stores_count}, "
            f"损益={result.loss_rows}, POS={result.pos_rows}, "
            f"月度={result.monthly_rows}, 宽表={result.unified_rows}, "
            f"错误={len(result.errors)}"
        )
        return result

    def run_stores(self, store_no: str | None = None) -> pd.DataFrame:
        """加载并写入门店主数据"""
        df = self.loader.load_stores(store_no)

        if self.mysql_writer and not df.empty:
            # 映射到 stores 表的列名
            mysql_df = df.rename(columns={
                "store_code": "store_code",
                "store_name": "store_name",
                "brand": "store_type",  # stores 表没有 brand 字段，暂存 store_type
            })
            self.mysql_writer.write_stores(mysql_df)

        if self.csv_writer and not df.empty:
            self.csv_writer.write_stores(df)

        return df

    def run_store_loss(
        self,
        date_range: tuple[str, str],
        perspective: str = "actual",
        store_no: str | None = None,
    ) -> pd.DataFrame:
        """加载并写入日损益数据"""
        df = self.loader.load_store_loss(store_no, date_range, perspective)

        if self.mysql_writer and not df.empty:
            # 映射到 store_daily_sales 表的列名
            mysql_df = df.rename(columns={
                "store_no": "store_code",
                "base_date": "sale_date",
                "sales_amount": "sales_amount",
                "gross_profit": "gross_profit",
                "operating_expense": "operating_expense",
            })
            self.mysql_writer.write_daily_sales(mysql_df)

        if self.csv_writer and not df.empty:
            self.csv_writer.write_daily_sales(df)

        return df

    def run_pos_orders(
        self,
        date_range: tuple[str, str],
        store_no: str | None = None,
    ) -> pd.DataFrame:
        """加载 POS 订单数据"""
        df = self.loader.load_pos_orders(store_no, date_range)

        if self.csv_writer and not df.empty:
            self.csv_writer.write(df, "pos_orders.csv")

        return df

    def run_monthly_metrics(
        self,
        date_range: tuple[str, str],
        store_no: str | None = None,
    ) -> pd.DataFrame:
        """加载并写入月度指标"""
        df = self.loader.load_monthly_metrics(store_no, date_range)

        if self.mysql_writer and not df.empty:
            self.mysql_writer.write_monthly_metrics(df)

        if self.csv_writer and not df.empty:
            self.csv_writer.write_monthly_metrics(df)

        return df

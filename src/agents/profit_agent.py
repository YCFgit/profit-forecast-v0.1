"""利润测算 Agent

职责：从统一宽表计算四层利润，支持双口径对比。
"""

import pandas as pd
from loguru import logger

from src.profit.profit_calculator import ProfitCalculator, ProfitSummary


class ProfitAgent:
    """利润测算 Agent"""

    def __init__(self):
        self.name = "ProfitAgent"
        self.calculator = ProfitCalculator()

    def calculate(self, sales_df: pd.DataFrame) -> ProfitSummary:
        """计算利润

        Args:
            sales_df: 统一销售宽表

        Returns:
            ProfitSummary
        """
        logger.info(f"[{self.name}] 开始利润测算: {sales_df['store_no'].nunique()} 家门店")

        summary = self.calculator.calculate_from_sales(sales_df)

        logger.info(
            f"[{self.name}] 利润测算完成: "
            f"总收入={summary.total_revenue:,.0f}, "
            f"净利润={summary.total_net_profit:,.0f}"
        )
        return summary

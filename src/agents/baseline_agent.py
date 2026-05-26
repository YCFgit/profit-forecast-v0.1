"""基线预估 Agent

职责：从销售数据推算基线收入和折扣预测。
"""

import pandas as pd
from loguru import logger

from src.forecasting.rules.baseline_engine import BaselineEngine


class BaselineAgent:
    """基线预估 Agent"""

    def __init__(self):
        self.name = "BaselineAgent"
        self.engine = BaselineEngine()

    def estimate(
        self,
        sales_df: pd.DataFrame,
        date_range: tuple = None,
    ) -> dict:
        """估算基线收入

        Args:
            sales_df: 统一销售宽表
            date_range: 预测目标日期范围

        Returns:
            {store_baselines: {store_no: baseline_revenue}, discount_forecasts: {...}}
        """
        logger.info(f"[{self.name}] 开始基线预估: {sales_df['store_no'].nunique()} 家门店")

        # 1. 基线收入估算
        store_baselines = {}
        for store_no in sales_df["store_no"].unique():
            store_data = sales_df[sales_df["store_no"] == store_no]
            baseline = self._estimate_store_baseline(store_no, store_data)
            store_baselines[store_no] = baseline

        # 2. 折扣预测
        discount_forecasts = {}
        try:
            # 从宽表的 avg_discount 字段做简单预测
            for brand in sales_df["brand"].unique():
                brand_data = sales_df[sales_df["brand"] == brand]
                avg_discount = brand_data["avg_discount"].mean()
                discount_forecasts[brand] = {
                    "current_avg_discount": round(avg_discount, 4),
                    "forecast_next_month": round(avg_discount * 0.98, 4),  # 简单趋势
                }
        except Exception as e:
            logger.warning(f"折扣预测失败: {e}")

        logger.info(f"[{self.name}] 基线预估完成: {len(store_baselines)} 家门店")
        return {
            "store_baselines": store_baselines,
            "discount_forecasts": discount_forecasts,
        }

    def _estimate_store_baseline(self, store_no: str, store_data: pd.DataFrame) -> float:
        """估算单店基线收入"""
        # 简单取最近 N 天的平均值 × 30
        recent = store_data.sort_values("base_date").tail(30)
        if recent.empty:
            return 0.0
        daily_avg = recent["revenue"].mean()
        return round(daily_avg * 30, 2)

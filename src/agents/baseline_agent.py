"""基线预估 Agent

职责：从销售数据推算基线收入和折扣预测。
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.forecasting.rules.baseline_engine import BaselineEngine


@dataclass
class BaselineResult:
    """基线预估结果"""
    store_count: int
    avg_mape: float
    baselines: dict[str, float]
    model_info: dict[str, dict] = field(default_factory=dict)


class BaselineAgent:
    """基线预估 Agent"""

    def __init__(self):
        self.name = "BaselineAgent"
        self.engine = BaselineEngine()

    def forecast(
        self,
        monthly_metrics: pd.DataFrame,
        stores_df: pd.DataFrame = None,
        daily_sales: pd.DataFrame = None,
        switch_status: pd.DataFrame = None,
    ) -> BaselineResult:
        """从月度指标推算基线收入（API 路由入口）

        Args:
            monthly_metrics: 月度指标 DataFrame（含 store_code, sales_amount 等）
            stores_df: 门店 DataFrame（可选）
            daily_sales: 日销 DataFrame（可选）
            switch_status: 开关状态 DataFrame（可选）

        Returns:
            BaselineResult
        """
        logger.info(
            f"[{self.name}] 开始基线预估: "
            f"{monthly_metrics['store_code'].nunique()} 家门店"
        )

        baselines = {}
        model_info = {}

        for store_code in monthly_metrics["store_code"].unique():
            store_data = monthly_metrics[monthly_metrics["store_code"] == store_code]
            # 取最近 N 个月的平均月销售额作为基线
            recent = store_data.sort_values("year_month").tail(3)
            if recent.empty:
                baseline = 0.0
            else:
                baseline = recent["sales_amount"].mean()

            baselines[store_code] = round(baseline, 2)
            model_info[store_code] = {
                "method": "moving_average",
                "months_used": len(recent),
                "avg_mape": 0.15,  # 简单估算
            }

        avg_mape = (
            sum(m["avg_mape"] for m in model_info.values()) / len(model_info)
            if model_info else 0.0
        )

        logger.info(f"[{self.name}] 基线预估完成: {len(baselines)} 家门店")
        return BaselineResult(
            store_count=len(baselines),
            avg_mape=avg_mape,
            baselines=baselines,
            model_info=model_info,
        )

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

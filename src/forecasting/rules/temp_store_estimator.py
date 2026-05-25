"""临时特卖店预估器

临时特卖店预估：近6个非春节月均值，不做季节修正。
临时特卖店不参与承压分配。
"""

from dataclasses import dataclass

import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar


@dataclass
class TempStoreEstimate:
    """临时特卖店预估结果"""
    store_code: str
    estimated_sales: float
    data_months: int
    participates_allocation: bool = False  # 临时特卖店不参与承压分配


class TempStoreEstimator:
    """临时特卖店预估器

    预估逻辑：
    1. 近6个非春节月均值
    2. 不做季节修正（临时店季节性不明显）
    3. 不参与承压分配

    使用方式：
        estimator = TempStoreEstimator()
        result = estimator.estimate(store_code, monthly_metrics, 2026, 5)
    """

    LOOKBACK_MONTHS = 6

    def __init__(self, lunar_calendar: LunarCalendar | None = None):
        self._lunar = lunar_calendar or LunarCalendar()

    def estimate(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> TempStoreEstimate:
        """临时特卖店预估"""
        values = self._get_recent_values(
            store_code, monthly_metrics_df, target_year, target_month,
        )

        if not values:
            return TempStoreEstimate(
                store_code=store_code,
                estimated_sales=0.0,
                data_months=0,
            )

        avg = sum(values) / len(values)

        return TempStoreEstimate(
            store_code=store_code,
            estimated_sales=round(avg, 2),
            data_months=len(values),
        )

    def _get_recent_values(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> list[float]:
        """获取近N个非春节月的销售值"""
        if monthly_metrics_df.empty or "store_code" not in monthly_metrics_df.columns:
            return []

        store_data = monthly_metrics_df[
            monthly_metrics_df["store_code"] == store_code
        ]
        if store_data.empty:
            return []

        months = []
        y, m = target_year, target_month
        for _ in range(self.LOOKBACK_MONTHS * 2):
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            if not self._lunar.is_spring_festival_month(y, m):
                months.append((y, m))
            if len(months) >= self.LOOKBACK_MONTHS:
                break

        values = []
        for yr, mo in months:
            ym_str = f"{yr}-{mo:02d}"
            row = store_data[store_data["year_month"] == ym_str]
            if row.empty or "sales_amount" not in row.columns:
                continue
            val = row["sales_amount"].iloc[0]
            if pd.notna(val) and val > 0:
                values.append(float(val))

        return values

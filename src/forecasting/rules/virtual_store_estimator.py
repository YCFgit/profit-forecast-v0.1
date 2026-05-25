"""虚拟店预估器

虚拟店预估：品牌×区域汇总，近6个非春节月去季节化均值。
虚拟店不单独参与承压分配，而是汇总到品牌×区域维度。
"""

from dataclasses import dataclass

import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar
from src.forecasting.rules.seasonal_index import SeasonalIndexTable


@dataclass
class VirtualStoreEstimate:
    """虚拟店预估结果"""
    store_code: str
    estimated_sales: float
    seasonal_index: float
    des_seasonal_sales: float
    data_months: int
    brand: str = ""
    region: str = ""


class VirtualStoreEstimator:
    """虚拟店预估器

    预估逻辑：
    1. 近6个非春节月去季节化均值
    2. 基线 = 去季节化均值 × 目标月季节指数

    使用方式：
        estimator = VirtualStoreEstimator(seasonal_table)
        result = estimator.estimate(store_code, monthly_metrics, 2026, 5, "品牌A", "华东")
    """

    LOOKBACK_MONTHS = 6

    def __init__(
        self,
        seasonal_table: SeasonalIndexTable,
        lunar_calendar: LunarCalendar | None = None,
    ):
        self._seasonal = seasonal_table
        self._lunar = lunar_calendar or LunarCalendar()

    def estimate(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str = "",
        region: str = "",
    ) -> VirtualStoreEstimate:
        """虚拟店预估"""
        sf = self._seasonal.get_factor(brand, region, target_month)

        des_values = self._get_recent_deseasonalized(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region,
        )

        if not des_values:
            return VirtualStoreEstimate(
                store_code=store_code,
                estimated_sales=0.0,
                seasonal_index=round(sf, 4),
                des_seasonal_sales=0.0,
                data_months=0,
                brand=brand,
                region=region,
            )

        des_avg = sum(des_values) / len(des_values)
        estimated = des_avg * sf

        return VirtualStoreEstimate(
            store_code=store_code,
            estimated_sales=round(estimated, 2),
            seasonal_index=round(sf, 4),
            des_seasonal_sales=round(des_avg, 2),
            data_months=len(des_values),
            brand=brand,
            region=region,
        )

    def _get_recent_deseasonalized(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
    ) -> list[float]:
        """获取近N个非春节月的去季节化值"""
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

        des_values = []
        for yr, mo in months:
            ym_str = f"{yr}-{mo:02d}"
            row = store_data[store_data["year_month"] == ym_str]
            if row.empty or "sales_amount" not in row.columns:
                continue
            val = row["sales_amount"].iloc[0]
            if pd.notna(val) and val > 0:
                sf = self._seasonal.get_factor(brand, region, mo)
                des = float(val) / sf if sf > 0 else float(val)
                des_values.append(des)

        return des_values

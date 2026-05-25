"""关店预估器

关店预估：正常月预估 × (营业天数/当月总天数) × 经验系数
"""

from dataclasses import dataclass

import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar
from src.forecasting.rules.seasonal_index import SeasonalIndexTable


@dataclass
class ClosingStoreEstimate:
    """关店预估结果"""
    store_code: str
    estimated_sales: float
    base_estimate: float       # 正常月预估
    operating_days: int        # 营业天数
    total_days: int            # 当月总天数
    day_ratio: float           # 营业天数比例
    closing_date: str | None = None


class ClosingStoreEstimator:
    """关店预估器

    预估逻辑：
    1. 使用近3个非春节月去季节化均值 × 目标月季节指数作为正常月预估
    2. 计算营业天数 = 关店日之前的天数（含关店日当天）
    3. 基线 = 正常月预估 × (营业天数/当月总天数) × 0.90 经验系数

    使用方式：
        estimator = ClosingStoreEstimator(seasonal_table)
        result = estimator.estimate(store_code, monthly_metrics, 2026, 5, "2026-05-15")
    """

    # 经验系数（关店月业绩通常低于按天数线性折算）
    CLOSING_RATIO = 0.90
    LOOKBACK_MONTHS = 3

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
        closing_date: str | None = None,
        brand: str = "",
        region: str = "",
    ) -> ClosingStoreEstimate:
        """关店预估

        Args:
            store_code: 门店编码
            monthly_metrics_df: 月度指标
            target_year: 预估年份
            target_month: 预估月份
            closing_date: 关店日期（字符串，如 "2026-05-15"）
            brand: 品牌
            region: 区域

        Returns:
            ClosingStoreEstimate
        """
        import calendar

        # 正常月预估（近3月去季节化均值 × 目标月季节指数）
        sf = self._seasonal.get_factor(brand, region, target_month)
        des_avg = self._get_deseasonalized_avg(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region,
        )
        base_estimate = des_avg * sf

        # 当月总天数
        total_days = calendar.monthrange(target_year, target_month)[1]

        # 营业天数
        if closing_date:
            try:
                cd = pd.Timestamp(closing_date)
                if cd.year == target_year and cd.month == target_month:
                    operating_days = cd.day
                elif cd < pd.Timestamp(target_year, target_month, 1):
                    operating_days = 0
                else:
                    operating_days = total_days
            except Exception:
                operating_days = total_days
        else:
            operating_days = total_days

        day_ratio = operating_days / total_days if total_days > 0 else 1.0
        estimated = base_estimate * day_ratio * self.CLOSING_RATIO

        return ClosingStoreEstimate(
            store_code=store_code,
            estimated_sales=round(estimated, 2),
            base_estimate=round(base_estimate, 2),
            operating_days=operating_days,
            total_days=total_days,
            day_ratio=round(day_ratio, 4),
            closing_date=closing_date,
        )

    def _get_deseasonalized_avg(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
    ) -> float:
        """近3个非春节月去季节化均值"""
        if monthly_metrics_df.empty or "store_code" not in monthly_metrics_df.columns:
            return 0.0

        store_data = monthly_metrics_df[
            monthly_metrics_df["store_code"] == store_code
        ]
        if store_data.empty:
            return 0.0

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

        return sum(des_values) / len(des_values) if des_values else 0.0

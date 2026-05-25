"""春节月专用预估

春节月的销售模式与平时差异大，季节指数和常规预估均排除春节月。
预估春节月本身时，使用历史春节月数据单独建模（均值法）。
"""

from dataclasses import dataclass

import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar


@dataclass
class SpringFestivalEstimate:
    """春节月预估结果"""
    store_code: str
    estimated_sales: float
    historical_avg: float
    historical_months: int  # 使用了几个历史春节月
    method: str = "spring_festival_mean"


class SpringFestivalEstimator:
    """春节月预估器

    预估逻辑：
    1. 收集该门店历史春节月的销售数据
    2. 计算历史春节月均值
    3. 如果历史春节月数据不足（<2个），使用近3个月均值 × 0.80 的经验系数

    使用方式：
        estimator = SpringFestivalEstimator()
        result = estimator.estimate(store_code, monthly_metrics, 2026, 2)
    """

    # 春节月经验系数（当历史数据不足时）
    FALLBACK_RATIO = 0.80

    def __init__(self, lunar_calendar: LunarCalendar | None = None):
        self._lunar = lunar_calendar or LunarCalendar()

    def estimate(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> SpringFestivalEstimate:
        """预估春节月销售

        Args:
            store_code: 门店编码
            monthly_metrics_df: 月度指标 DataFrame
            target_year: 预估年份
            target_month: 预估月份

        Returns:
            SpringFestivalEstimate
        """
        if monthly_metrics_df.empty:
            return SpringFestivalEstimate(
                store_code=store_code,
                estimated_sales=0.0,
                historical_avg=0.0,
                historical_months=0,
            )

        # 收集历史春节月数据
        sf_sales = self._collect_spring_festival_months(
            store_code, monthly_metrics_df, target_year
        )

        if len(sf_sales) >= 2:
            # 有足够历史春节月数据
            avg = sum(sf_sales) / len(sf_sales)
            return SpringFestivalEstimate(
                store_code=store_code,
                estimated_sales=round(avg, 2),
                historical_avg=round(avg, 2),
                historical_months=len(sf_sales),
                method="spring_festival_mean",
            )

        # 历史数据不足，使用近3个月均值 × 经验系数
        recent_avg = self._calc_recent_avg(store_code, monthly_metrics_df, target_year, target_month)
        fallback = recent_avg * self.FALLBACK_RATIO

        return SpringFestivalEstimate(
            store_code=store_code,
            estimated_sales=round(fallback, 2),
            historical_avg=round(fallback, 2),
            historical_months=len(sf_sales),
            method="recent_mean_fallback",
        )

    def estimate_batch(
        self,
        store_codes: list[str],
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> dict[str, SpringFestivalEstimate]:
        """批量预估春节月

        Returns:
            {store_code: SpringFestivalEstimate}
        """
        results = {}
        for code in store_codes:
            results[code] = self.estimate(
                code, monthly_metrics_df, target_year, target_month
            )
        return results

    def _collect_spring_festival_months(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
    ) -> list[float]:
        """收集历史春节月销售数据

        收集 target_year 之前所有春节月的数据
        """
        if monthly_metrics_df.empty or "store_code" not in monthly_metrics_df.columns:
            return []

        store_data = monthly_metrics_df[
            monthly_metrics_df["store_code"] == store_code
        ]

        if store_data.empty:
            return []

        sf_sales = []
        for year in range(2020, target_year):
            sf = self._lunar.get_spring_festival(year)
            if sf is None:
                continue
            sf_month = sf[0]
            ym_str = f"{year}-{sf_month:02d}"
            row = store_data[store_data["year_month"] == ym_str]
            if not row.empty and "sales_amount" in row.columns:
                val = row["sales_amount"].iloc[0]
                if pd.notna(val) and val > 0:
                    sf_sales.append(float(val))

        return sf_sales

    def _calc_recent_avg(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> float:
        """计算近3个非春节月均值"""
        store_data = monthly_metrics_df[
            monthly_metrics_df["store_code"] == store_code
        ]

        if store_data.empty:
            return 0.0

        # 生成近3个月
        months = []
        y, m = target_year, target_month
        for _ in range(6):  # 多取几个以排除春节月
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            if not self._lunar.is_spring_festival_month(y, m):
                months.append((y, m))
            if len(months) >= 3:
                break

        sales = []
        for yr, mo in months:
            ym_str = f"{yr}-{mo:02d}"
            row = store_data[store_data["year_month"] == ym_str]
            if not row.empty and "sales_amount" in row.columns:
                val = row["sales_amount"].iloc[0]
                if pd.notna(val) and val > 0:
                    sales.append(float(val))

        return sum(sales) / len(sales) if sales else 0.0

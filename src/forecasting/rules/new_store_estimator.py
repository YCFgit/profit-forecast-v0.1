"""新店预估器

新店预估：同品牌×同区域成熟大中店中位数 × 爬坡系数（根据开业月龄）
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.forecasting.rules.seasonal_index import SeasonalIndexTable


@dataclass
class NewStoreEstimate:
    """新店预估结果"""
    store_code: str
    estimated_sales: float
    reference_median: float     # 同品牌×区域成熟大中店中位数
    ramp_coefficient: float     # 爬坡系数
    opening_months: int         # 开业月龄
    brand: str = ""
    region: str = ""


class NewStoreEstimator:
    """新店预估器

    预估逻辑：
    1. 找到同品牌×同区域的成熟大中店
    2. 计算这些店的月均业绩中位数
    3. 根据开业月龄确定爬坡系数
    4. 基线 = 中位数 × 爬坡系数

    爬坡系数表：
    - 0-3个月：0.40
    - 4-6个月：0.60
    - 7-12个月：0.80
    - 13-24个月：0.90
    - 24个月以上：1.00（不再是新店）

    使用方式：
        estimator = NewStoreEstimator(seasonal_table)
        result = estimator.estimate(store_code, stores_df, monthly_metrics, 2026, 5)
    """

    # 爬坡系数表：(最大月龄, 系数)
    RAMP_TABLE: list[tuple[int, float]] = [
        (3, 0.40),
        (6, 0.60),
        (12, 0.80),
        (24, 0.90),
    ]

    DEFAULT_RAMP = 1.00

    def __init__(self, seasonal_table: SeasonalIndexTable):
        self._seasonal = seasonal_table

    def estimate(
        self,
        store_code: str,
        stores_df: pd.DataFrame,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str = "",
        region: str = "",
        opening_date: str | None = None,
    ) -> NewStoreEstimate:
        """新店预估

        Args:
            store_code: 门店编码
            stores_df: 门店主数据（用于找同品牌×区域的大中店）
            monthly_metrics_df: 月度指标
            target_year: 预估年份
            target_month: 预估月份
            brand: 品牌
            region: 区域
            opening_date: 开业日期（字符串，如 "2025-06-01"）

        Returns:
            NewStoreEstimate
        """
        # 计算开业月龄
        opening_months = self._calc_opening_months(
            opening_date, target_year, target_month
        )

        # 爬坡系数
        ramp = self._get_ramp_coefficient(opening_months)

        # 同品牌×区域成熟大中店的月均业绩
        reference_median = self._calc_reference_median(
            stores_df, monthly_metrics_df, brand, region,
        )

        estimated = reference_median * ramp

        return NewStoreEstimate(
            store_code=store_code,
            estimated_sales=round(estimated, 2),
            reference_median=round(reference_median, 2),
            ramp_coefficient=ramp,
            opening_months=opening_months,
            brand=brand,
            region=region,
        )

    def _calc_opening_months(
        self,
        opening_date: str | None,
        target_year: int,
        target_month: int,
    ) -> int:
        """计算开业月龄"""
        if not opening_date:
            return 24  # 默认视为成熟店

        try:
            od = pd.Timestamp(opening_date)
            target = pd.Timestamp(target_year, target_month, 1)
            delta = (target.year - od.year) * 12 + (target.month - od.month)
            return max(0, delta)
        except Exception:
            return 24

    def _get_ramp_coefficient(self, opening_months: int) -> float:
        """根据开业月龄获取爬坡系数"""
        for max_months, coeff in self.RAMP_TABLE:
            if opening_months <= max_months:
                return coeff
        return self.DEFAULT_RAMP

    def _calc_reference_median(
        self,
        stores_df: pd.DataFrame,
        monthly_metrics_df: pd.DataFrame,
        brand: str,
        region: str,
    ) -> float:
        """计算同品牌×区域成熟大中店的月均业绩中位数

        "成熟"定义：开业超过24个月且近期月均 >= 3万
        """
        if stores_df.empty or monthly_metrics_df.empty:
            return 0.0

        # 找同品牌×区域的门店
        same_group = stores_df[
            (stores_df["brand"] == brand) & (stores_df["region"] == region)
        ]

        if same_group.empty:
            # 回退到同品牌
            same_group = stores_df[stores_df["brand"] == brand]

        if same_group.empty:
            return 0.0

        # 计算每家店的月均业绩
        monthly_avgs = []
        for _, store in same_group.iterrows():
            code = store["store_code"]
            store_data = monthly_metrics_df[
                monthly_metrics_df["store_code"] == code
            ]
            if store_data.empty or "sales_amount" not in store_data.columns:
                continue

            avg = store_data["sales_amount"].mean()
            if pd.notna(avg) and avg >= 30_000:  # 月均 >= 3万
                monthly_avgs.append(float(avg))

        if not monthly_avgs:
            return 0.0

        return float(np.median(monthly_avgs))

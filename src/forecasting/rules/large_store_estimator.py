"""大中店预估器 — 三机制预估

机制一：当月前12天推全月（仅预估当月且有 ≥12天数据时）
机制二：结构性变化检测（近3月 vs 近12月 去季节化比值）
机制三：加权近月预估（6个月权重：0.35, 0.25, 0.18, 0.12, 0.07, 0.03）
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar
from src.forecasting.rules.seasonal_index import SeasonalIndexTable


@dataclass
class LargeStoreEstimate:
    """大中店预估结果"""
    store_code: str
    mechanism_used: str              # "current_month_push" | "structural_change" | "weighted_recent"
    estimated_sales: float
    seasonal_index: float
    des_seasonal_sales: float        # 去季节化值
    structural_ratio: float | None = None
    data_window_months: int = 0
    excluded_months: list[str] | None = None
    confidence: str = "medium"       # "high" | "medium" | "low"


class LargeStoreEstimator:
    """大中店预估器

    三机制：
    1. 当月前12天推全月（仅预估当月且有≥12天数据时）
    2. 结构性变化检测（ratio < 0.70 或 > 1.30 → 仅用近3个月）
    3. 加权近月预估

    使用方式：
        estimator = LargeStoreEstimator(seasonal_table)
        result = estimator.estimate(store_code, monthly_metrics, daily_sales, 2026, 5)
    """

    # 加权近月权重（从近到远）
    RECENT_WEIGHTS = [0.35, 0.25, 0.18, 0.12, 0.07, 0.03]

    # 结构性变化阈值
    STRUCTURAL_LOW = 0.70
    STRUCTURAL_HIGH = 1.30

    # 当月推全月最少天数
    MIN_DAYS_FOR_PUSH = 12

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
        daily_sales_df: pd.DataFrame | None,
        target_year: int,
        target_month: int,
        brand: str = "",
        region: str = "",
    ) -> LargeStoreEstimate:
        """大中店预估

        Args:
            store_code: 门店编码
            monthly_metrics_df: 月度指标 DataFrame
            daily_sales_df: 日销 DataFrame（用于机制一）
            target_year: 预估年份
            target_month: 预估月份
            brand: 品牌
            region: 区域

        Returns:
            LargeStoreEstimate
        """
        # 获取目标月季节因子
        sf = self._seasonal.get_factor(brand, region, target_month)

        # 机制一：当月推全月
        if self._is_current_month(target_year, target_month):
            push_result = self._try_current_month_push(
                store_code, daily_sales_df, monthly_metrics_df,
                target_year, target_month, sf, brand, region,
            )
            if push_result is not None:
                return push_result

        # 机制二：结构性变化检测
        structural_ratio, use_short_window = self._detect_structural_change(
            store_code, monthly_metrics_df, target_year, target_month, brand, region,
        )

        # 机制三：加权近月预估
        return self._weighted_recent_estimate(
            store_code=store_code,
            monthly_metrics_df=monthly_metrics_df,
            target_year=target_year,
            target_month=target_month,
            brand=brand,
            region=region,
            seasonal_factor=sf,
            structural_ratio=structural_ratio,
            use_short_window=use_short_window,
        )

    def _is_current_month(self, target_year: int, target_month: int) -> bool:
        """判断是否为当前月"""
        from datetime import date
        today = date.today()
        return today.year == target_year and today.month == target_month

    def _try_current_month_push(
        self,
        store_code: str,
        daily_sales_df: pd.DataFrame | None,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        seasonal_factor: float,
        brand: str,
        region: str,
    ) -> LargeStoreEstimate | None:
        """机制一：当月前12天推全月

        Returns:
            LargeStoreEstimate 或 None（数据不足时）
        """
        if daily_sales_df is None or daily_sales_df.empty:
            return None

        # 获取当月日销数据
        store_daily = daily_sales_df[
            daily_sales_df["store_code"] == store_code
        ].copy()

        if store_daily.empty:
            return None

        # 解析日期
        if "sale_date" in store_daily.columns:
            store_daily["sale_date"] = pd.to_datetime(store_daily["sale_date"])
            # 筛选当月数据
            mask = (
                (store_daily["sale_date"].dt.year == target_year)
                & (store_daily["sale_date"].dt.month == target_month)
            )
            month_data = store_daily[mask]

            if len(month_data) < self.MIN_DAYS_FOR_PUSH:
                return None

            # 前12天累计
            first_12 = month_data.head(self.MIN_DAYS_FOR_PUSH)
            actual_12d = first_12["sales_amount"].sum()

            # 计算期望值（工作日/周末区分）
            # 简化处理：使用上月日均
            last_month_sales = self._get_last_month_sales(
                store_code, monthly_metrics_df, target_year, target_month
            )
            if last_month_sales <= 0:
                return None

            # 上月天数估算
            last_m = target_month - 1 if target_month > 1 else 12
            last_y = target_year if target_month > 1 else target_year - 1
            import calendar
            last_month_days = calendar.monthrange(last_y, last_m)[1]
            last_daily_avg = last_month_sales / last_month_days

            # 前12天期望值
            expected_12d = last_daily_avg * self.MIN_DAYS_FOR_PUSH

            # 比例因子
            ratio = actual_12d / expected_12d if expected_12d > 0 else 1.0

            # 推算全月
            import calendar
            total_days = calendar.monthrange(target_year, target_month)[1]
            remaining_days = total_days - self.MIN_DAYS_FOR_PUSH
            remaining_expected = last_daily_avg * remaining_days * ratio
            full_month = actual_12d + remaining_expected

            # 合理性检查：去季节化后不应超过近期中位数的2倍
            des_sales = full_month / seasonal_factor if seasonal_factor > 0 else full_month
            recent_median = self._get_recent_median(
                store_code, monthly_metrics_df, target_year, target_month, brand, region
            )
            if recent_median > 0 and des_sales > recent_median * 2:
                return None  # 不合理，回退到机制三

            return LargeStoreEstimate(
                store_code=store_code,
                mechanism_used="current_month_push",
                estimated_sales=round(full_month, 2),
                seasonal_index=round(seasonal_factor, 4),
                des_seasonal_sales=round(des_sales, 2),
                data_window_months=1,
                confidence="high",
            )

        return None

    def _detect_structural_change(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
    ) -> tuple[float | None, bool]:
        """机制二：结构性变化检测

        Returns:
            (structural_ratio, use_short_window)
        """
        # 近3月去季节化均值
        recent_3 = self._get_deseasonalized_avg(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region, lookback=3,
        )
        # 近12月去季节化均值
        recent_12 = self._get_deseasonalized_avg(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region, lookback=12,
        )

        if recent_12 <= 0:
            return None, False

        ratio = recent_3 / recent_12
        use_short_window = ratio < self.STRUCTURAL_LOW or ratio > self.STRUCTURAL_HIGH

        return round(ratio, 4), use_short_window

    def _weighted_recent_estimate(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
        seasonal_factor: float,
        structural_ratio: float | None,
        use_short_window: bool,
    ) -> LargeStoreEstimate:
        """机制三：加权近月预估"""
        # 确定回溯窗口
        window = 3 if use_short_window else 6

        # 获取近N个月的去季节化值
        des_values = self._get_recent_deseasonalized(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region, lookback=window,
        )

        if not des_values:
            return LargeStoreEstimate(
                store_code=store_code,
                mechanism_used="weighted_recent",
                estimated_sales=0.0,
                seasonal_index=round(seasonal_factor, 4),
                des_seasonal_sales=0.0,
                structural_ratio=structural_ratio,
                data_window_months=0,
                confidence="low",
            )

        # 加权平均
        weights = self.RECENT_WEIGHTS[:len(des_values)]
        weight_sum = sum(weights)
        weighted_avg = sum(v * w for v, w in zip(des_values, weights)) / weight_sum

        # 基线预估 = 加权基准 × 目标月季节指数
        estimated = weighted_avg * seasonal_factor

        confidence = "medium"
        if len(des_values) >= 6:
            confidence = "high"
        elif len(des_values) < 3:
            confidence = "low"

        return LargeStoreEstimate(
            store_code=store_code,
            mechanism_used="weighted_recent",
            estimated_sales=round(estimated, 2),
            seasonal_index=round(seasonal_factor, 4),
            des_seasonal_sales=round(weighted_avg, 2),
            structural_ratio=structural_ratio,
            data_window_months=len(des_values),
            confidence=confidence,
        )

    def _get_last_month_sales(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
    ) -> float:
        """获取上月销售额"""
        m = target_month - 1 if target_month > 1 else 12
        y = target_year if target_month > 1 else target_year - 1
        ym = f"{y}-{m:02d}"

        store_data = monthly_metrics_df[monthly_metrics_df["store_code"] == store_code]
        row = store_data[store_data["year_month"] == ym]
        if row.empty or "sales_amount" not in row.columns:
            return 0.0
        val = row["sales_amount"].iloc[0]
        return float(val) if pd.notna(val) else 0.0

    def _get_recent_median(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
    ) -> float:
        """获取近期去季节化中位数"""
        des_values = self._get_recent_deseasonalized(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region, lookback=6,
        )
        if not des_values:
            return 0.0
        return float(np.median(des_values))

    def _get_deseasonalized_avg(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
        lookback: int,
    ) -> float:
        """获取近N个月的去季节化均值"""
        des_values = self._get_recent_deseasonalized(
            store_code, monthly_metrics_df, target_year, target_month,
            brand, region, lookback=lookback,
        )
        return sum(des_values) / len(des_values) if des_values else 0.0

    def _get_recent_deseasonalized(
        self,
        store_code: str,
        monthly_metrics_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        brand: str,
        region: str,
        lookback: int,
    ) -> list[float]:
        """获取近N个月的去季节化值列表"""
        if monthly_metrics_df.empty or "store_code" not in monthly_metrics_df.columns:
            return []

        store_data = monthly_metrics_df[
            monthly_metrics_df["store_code"] == store_code
        ]
        if store_data.empty:
            return []

        # 生成回溯月列表（排除春节月）
        months = []
        y, m = target_year, target_month
        for _ in range(lookback * 2):  # 多取以排除春节
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            if not self._lunar.is_spring_festival_month(y, m):
                months.append((y, m))
            if len(months) >= lookback:
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

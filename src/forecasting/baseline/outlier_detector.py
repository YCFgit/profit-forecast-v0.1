"""异常值检测器

基于 IQR 方法检测极端值，支持：
- 标记大促期间（618/双11/年货节）不作为异常剔除
- 标记闭店/装修期间自动排除
- 可配置敏感度
"""

from datetime import date
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger


# 大促期间定义（月-日范围）
PROMOTION_PERIODS = [
    {"name": "年货节", "start": (1, 1), "end": (2, 15)},
    {"name": "38女王节", "start": (3, 1), "end": (3, 10)},
    {"name": "618", "start": (6, 1), "end": (6, 20)},
    {"name": "818", "start": (8, 10), "end": (8, 20)},
    {"name": "双11", "start": (11, 1), "end": (11, 15)},
    {"name": "双12", "start": (12, 5), "end": (12, 15)},
]

# 节假日
HOLIDAYS = [
    {"name": "春节", "start": (1, 20), "end": (2, 10)},
    {"name": "五一", "start": (5, 1), "end": (5, 5)},
    {"name": "十一", "start": (10, 1), "end": (10, 7)},
    {"name": "中秋", "variable": True},  # 需要农历计算，简化处理
]


@dataclass
class OutlierResult:
    """异常值检测结果"""
    total_points: int
    outlier_count: int
    promotion_count: int
    closure_count: int
    outlier_indices: list[int] = field(default_factory=list)
    promotion_indices: list[int] = field(default_factory=list)
    closure_indices: list[int] = field(default_factory=list)

    @property
    def outlier_rate(self) -> float:
        return self.outlier_count / self.total_points if self.total_points > 0 else 0


class OutlierDetector:
    """异常值检测器

    使用方式：
        detector = OutlierDetector(iqr_factor=1.5)
        clean_series, result = detector.detect(series, store_open_dates)
    """

    def __init__(
        self,
        iqr_factor: float = 1.5,
        min_data_points: int = 10,
        promotion_multiplier: float = 2.0,
    ):
        """
        Args:
            iqr_factor: IQR 系数，越大越宽松（1.5=标准，2.0=宽松）
            min_data_points: 最少数据点数
            promotion_multiplier: 大促期间的容忍倍数（相对于 IQR）
        """
        self.iqr_factor = iqr_factor
        self.min_data_points = min_data_points
        self.promotion_multiplier = promotion_multiplier

    def detect(
        self,
        series: pd.Series,
        dates: pd.DatetimeIndex | None = None,
        closure_periods: list[tuple[date, date]] | None = None,
    ) -> tuple[pd.Series, OutlierResult]:
        """检测并处理异常值

        Args:
            series: 时间序列数据（index 为日期）
            dates: 日期索引（如果 series 的 index 不是日期）
            closure_periods: 闭店/装修期间列表 [(start, end), ...]

        Returns:
            (清洗后的序列, 检测结果)
        """
        if dates is not None:
            series = series.copy()
            series.index = dates

        if len(series) < self.min_data_points:
            logger.warning(f"数据点不足 ({len(series)} < {self.min_data_points})，跳过异常检测")
            return series, OutlierResult(
                total_points=len(series), outlier_count=0,
                promotion_count=0, closure_count=0
            )

        result = OutlierResult(total_points=len(series), outlier_count=0, promotion_count=0, closure_count=0)
        clean = series.copy()

        # Step 1: 标记闭店期间
        closure_mask = self._mark_closure(series.index, closure_periods)
        result.closure_count = closure_mask.sum()
        result.closure_indices = list(np.where(closure_mask)[0])

        # Step 2: 标记大促期间
        promotion_mask = self._mark_promotion(series.index)
        result.promotion_count = promotion_mask.sum()
        result.promotion_indices = list(np.where(promotion_mask)[0])

        # Step 3: IQR 检测（排除闭店和大促数据）
        normal_mask = ~closure_mask & ~promotion_mask
        normal_data = series[normal_mask]

        if len(normal_data) < self.min_data_points:
            logger.warning("正常数据点不足，使用全部数据计算 IQR")
            normal_data = series

        q1 = normal_data.quantile(0.25)
        q3 = normal_data.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - self.iqr_factor * iqr
        upper = q3 + self.iqr_factor * iqr

        # Step 4: 标记异常值
        outlier_mask = pd.Series(False, index=series.index)

        # 非大促期间的异常值
        outlier_mask[normal_mask] = (series[normal_mask] < lower) | (series[normal_mask] > upper)

        # 大促期间使用更宽松的阈值
        promo_lower = q1 - self.iqr_factor * self.promotion_multiplier * iqr
        promo_upper = q3 + self.iqr_factor * self.promotion_multiplier * iqr
        outlier_mask[promotion_mask] = (series[promotion_mask] < promo_lower) | (series[promotion_mask] > promo_upper)

        result.outlier_count = outlier_mask.sum()
        result.outlier_indices = list(np.where(outlier_mask)[0])

        # Step 5: 处理异常值（用前后值的中位数替代）
        for idx in result.outlier_indices:
            clean.iloc[idx] = self._interpolate_value(series, idx, outlier_mask)

        # Step 6: 闭店期间设为 NaN
        clean[closure_mask] = np.nan

        logger.info(
            f"异常检测: 总{result.total_points}点, "
            f"异常{result.outlier_count}个({result.outlier_rate:.1%}), "
            f"大促{result.promotion_count}个, 闭店{result.closure_count}个"
        )

        return clean, result

    def _mark_promotion(self, index: pd.DatetimeIndex) -> pd.Series:
        """标记大促期间"""
        mask = pd.Series(False, index=index)
        for period in PROMOTION_PERIODS:
            sm, sd = period["start"]
            em, ed = period["end"]
            for i, dt in enumerate(index):
                if sm <= dt.month <= em and (
                    (dt.month == sm and dt.day >= sd) or
                    (dt.month == em and dt.day <= ed) or
                    (sm < dt.month < em)
                ):
                    mask.iloc[i] = True
        return mask

    def _mark_closure(
        self, index: pd.DatetimeIndex, closure_periods: list[tuple[date, date]] | None
    ) -> pd.Series:
        """标记闭店期间"""
        mask = pd.Series(False, index=index)
        if closure_periods:
            for start, end in closure_periods:
                mask[(index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))] = True
        return mask

    def _interpolate_value(self, series: pd.Series, idx: int, outlier_mask: pd.Series) -> float:
        """插值替代异常值"""
        # 取前后各 3 个正常值的中位数
        window = 3
        values = []
        for offset in range(1, window + 1):
            if idx - offset >= 0 and not outlier_mask.iloc[idx - offset]:
                values.append(series.iloc[idx - offset])
            if idx + offset < len(series) and not outlier_mask.iloc[idx + offset]:
                values.append(series.iloc[idx + offset])
        return float(np.median(values)) if values else float(series.median())

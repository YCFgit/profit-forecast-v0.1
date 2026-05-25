"""季节性分解与季节因子计算

鞋服行业强季节性：
- Q4 旺季（秋冬装客单价高）
- Q1 淡季（春节后）
- 618/双11 大促脉冲

支持按品类分别计算季节性指数。
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class SeasonalResult:
    """季节性分解结果"""
    seasonal_index: dict[int, float]   # 月份 → 季节因子 (1.0 = 无季节性)
    trend: pd.Series                   # 趋势分量
    residual: pd.Series                # 残差分量
    strength: float                    # 季节性强度 (0-1, 越大季节性越强)

    def get_factor(self, month: int) -> float:
        """获取某月的季节因子"""
        return self.seasonal_index.get(month, 1.0)


class SeasonalDecomposer:
    """季节性分解器

    使用方式：
        decomposer = SeasonalDecomposer()
        result = decomposer.decompose(monthly_series)
    """

    def __init__(
        self,
        method: Literal["additive", "multiplicative"] = "multiplicative",
        min_periods: int = 12,
    ):
        """
        Args:
            method: 分解方法
                - additive: 加法模型 Y = T + S + R
                - multiplicative: 乘法模型 Y = T × S × R（鞋服推荐）
            min_periods: 最少月数（至少 12 个月才能计算季节性）
        """
        self.method = method
        self.min_periods = min_periods

    def decompose(self, monthly_series: pd.Series) -> SeasonalResult:
        """分解月度时间序列

        Args:
            monthly_series: 月度数据，index 为 datetime 或 period，值为销售额

        Returns:
            SeasonalResult
        """
        if len(monthly_series) < self.min_periods:
            logger.warning(f"数据不足 {self.min_periods} 个月，跳过季节性分解")
            return SeasonalResult(
                seasonal_index={i: 1.0 for i in range(1, 13)},
                trend=monthly_series,
                residual=pd.Series(0, index=monthly_series.index),
                strength=0.0,
            )

        series = monthly_series.copy()
        if not isinstance(series.index, pd.DatetimeIndex):
            series.index = pd.to_datetime(series.index)

        # Step 1: 趋势提取（12 个月移动平均）
        trend = self._extract_trend(series)

        # Step 2: 去趋势
        if self.method == "multiplicative":
            detrended = series / trend
        else:
            detrended = series - trend

        # Step 3: 计算季节因子（各月平均值）
        detrended_months = detrended.groupby(detrended.index.month).mean()

        if self.method == "multiplicative":
            # 乘法模型：归一化使季节因子均值为 1.0
            seasonal_index = (detrended_months / detrended_months.mean()).to_dict()
        else:
            # 加法模型：季节因子均值为 0
            seasonal_index = (detrended_months - detrended_months.mean()).to_dict()

        # Step 4: 残差
        seasonal_series = pd.Series(
            [seasonal_index.get(m, 1.0) for m in series.index.month],
            index=series.index,
        )
        if self.method == "multiplicative":
            residual = series / (trend * seasonal_series)
        else:
            residual = series - trend - seasonal_series

        # Step 5: 季节性强度
        strength = self._calc_strength(series, seasonal_series, residual)

        result = SeasonalResult(
            seasonal_index=seasonal_index,
            trend=trend,
            residual=residual,
            strength=strength,
        )

        logger.info(
            f"季节性分解: 方法={self.method}, 强度={strength:.2f}, "
            f"最大因子={max(seasonal_index.values()):.3f}({max(seasonal_index, key=seasonal_index.get)}月), "
            f"最小因子={min(seasonal_index.values()):.3f}({min(seasonal_index, key=seasonal_index.get)}月)"
        )

        return result

    def _extract_trend(self, series: pd.Series) -> pd.Series:
        """提取趋势分量（12 个月居中移动平均）"""
        if self.method == "multiplicative":
            trend = series.rolling(window=12, center=True, min_periods=6).mean()
        else:
            trend = series.rolling(window=12, center=True, min_periods=6).mean()
        # 填充首尾
        trend = trend.bfill().ffill()
        return trend

    def _calc_strength(
        self, original: pd.Series, seasonal: pd.Series, residual: pd.Series
    ) -> float:
        """计算季节性强度

        强度 = 1 - Var(R) / Var(Y - T)
        值越大说明季节性越强
        """
        if self.method == "multiplicative":
            var_r = np.var(residual.dropna())
            var_st = np.var((original / self._extract_trend(original)).dropna())
        else:
            var_r = np.var(residual.dropna())
            var_st = np.var((original - self._extract_trend(original)).dropna())

        if var_st == 0:
            return 0.0
        return max(0.0, min(1.0, 1 - var_r / var_st))


def get_shoe_seasonal_default() -> dict[int, float]:
    """鞋服行业默认季节因子（基于行业经验）

    Q4 秋冬旺季: 1.15-1.30
    Q1 春节淡季: 0.70-0.85
    Q2 春夏过渡: 0.90-1.00
    Q3 夏季: 0.85-0.95
    """
    return {
        1: 0.75,   # 春节前淡季
        2: 0.70,   # 春节最淡
        3: 0.85,   # 换季启动
        4: 0.95,   # 春装上新
        5: 1.00,   # 正常
        6: 1.10,   # 618 大促
        7: 0.90,   # 夏季淡季
        8: 0.88,   # 暑期
        9: 0.95,   # 秋装上新
        10: 1.05,  # 国庆
        11: 1.25,  # 双11 + 冬装旺季
        12: 1.30,  # 年末旺季
    }

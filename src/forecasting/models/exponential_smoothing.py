"""指数平滑模型封装

基于 statsmodels 的 Holt-Winters 指数平滑。
适合趋势+季节性数据，计算速度快。
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ExponentialSmoothingConfig:
    """指数平滑配置"""
    trend: Literal["add", "mul", None] = "add"
    seasonal: Literal["add", "mul", None] = "mul"
    seasonal_periods: int = 12
    damped_trend: bool = True  # 阻尼趋势（防止过度外推）


class ExponentialSmoothingModel:
    """Holt-Winters 指数平滑模型

    计算速度快，适合 500+ 门店批量预测。

    使用方式：
        model = ExponentialSmoothingModel()
        forecast = model.fit_predict(train_series, forecast_periods=3)
    """

    name = "ExpSmoothing"

    def __init__(self, config: ExponentialSmoothingConfig | None = None):
        self.config = config or ExponentialSmoothingConfig()
        self._fitted = None

    def fit_predict(
        self,
        train_series: pd.Series,
        forecast_periods: int = 3,
    ) -> pd.Series:
        """拟合并预测"""
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
        except ImportError:
            logger.error("statsmodels 未安装")
            return self._fallback_predict(train_series, forecast_periods)

        series = train_series.dropna()
        if len(series) < 6:
            return self._fallback_predict(series, forecast_periods)

        # 数据至少 2 个完整季节周期才用季节性
        use_seasonal = self.config.seasonal is not None and len(series) >= 2 * self.config.seasonal_periods

        try:
            model = ExponentialSmoothing(
                series,
                trend=self.config.trend,
                seasonal=self.config.seasonal if use_seasonal else None,
                seasonal_periods=self.config.seasonal_periods if use_seasonal else None,
                damped_trend=self.config.damped_trend,
            )
            fitted = model.fit(optimized=True)
            forecast = fitted.forecast(forecast_periods)
            forecast = forecast.clip(lower=0)

            self._fitted = fitted

            logger.info(
                f"指数平滑拟合完成, 季节性={'是' if use_seasonal else '否'}, "
                f"预测{forecast_periods}个月"
            )
            return forecast

        except Exception as e:
            logger.warning(f"指数平滑拟合失败: {e}")
            return self._fallback_predict(series, forecast_periods)

    def _fallback_predict(self, series: pd.Series, periods: int) -> pd.Series:
        """回退预测"""
        clean = series.dropna()
        if len(clean) == 0:
            return pd.Series(0, index=pd.date_range(periods=periods, freq="MS"))
        recent = clean.tail(3)
        mean_val = recent.mean()
        last_date = clean.index[-1]
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq="MS")[1:]
        return pd.Series([mean_val] * periods, index=future_dates)

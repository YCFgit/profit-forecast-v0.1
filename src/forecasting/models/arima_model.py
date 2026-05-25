"""ARIMA 模型封装

基于 statsmodels 的 ARIMA/SARIMA 模型。
支持自动参数选择（基于 AIC）。
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ARIMAConfig:
    """ARIMA 配置"""
    max_p: int = 3          # AR 阶数上限
    max_d: int = 2          # 差分次数上限
    max_q: int = 3          # MA 阶数上限
    seasonal: bool = True   # 是否使用季节性 ARIMA
    seasonal_period: int = 12  # 季节周期（月度=12）
    max_P: int = 1          # 季节 AR 阶数上限
    max_D: int = 1          # 季节差分上限
    max_Q: int = 1          # 季节 MA 阶数上限
    information_criterion: str = "aic"  # 信息准则


class ARIMAModel:
    """ARIMA/SARIMA 时间序列预测模型

    自动搜索最优参数，支持季节性建模。

    使用方式：
        model = ARIMAModel()
        forecast = model.fit_predict(train_series, forecast_periods=3)
    """

    name = "ARIMA"

    def __init__(self, config: ARIMAConfig | None = None):
        self.config = config or ARIMAConfig()
        self._model = None
        self._fitted = None
        self._best_order = None
        self._best_seasonal_order = None

    def fit_predict(
        self,
        train_series: pd.Series,
        forecast_periods: int = 3,
        exog: pd.DataFrame | None = None,
    ) -> pd.Series:
        """拟合并预测

        Args:
            train_series: 训练数据（月度序列）
            forecast_periods: 预测月数
            exog: 外生变量（可选）

        Returns:
            预测序列
        """
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            logger.error("statsmodels 未安装，无法使用 ARIMA 模型")
            return pd.Series(dtype=float)

        series = train_series.dropna()
        if len(series) < 6:
            logger.warning("数据不足 6 个月，使用简单均值预测")
            return self._fallback_predict(series, forecast_periods)

        # 自动选择参数
        best_order, best_seasonal_order = self._auto_select_params(series)

        try:
            model = SARIMAX(
                series,
                order=best_order,
                seasonal_order=best_seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit(disp=False, maxiter=200)

            # 预测
            forecast = fitted.forecast(steps=forecast_periods)
            forecast = forecast.clip(lower=0)  # 销售额不能为负

            self._model = model
            self._fitted = fitted
            self._best_order = best_order
            self._best_seasonal_order = best_seasonal_order

            logger.info(
                f"ARIMA{best_order}x{best_seasonal_order} 拟合完成, "
                f"AIC={fitted.aic:.1f}, 预测{forecast_periods}个月"
            )

            return forecast

        except Exception as e:
            logger.warning(f"ARIMA 拟合失败: {e}，回退到简单方法")
            return self._fallback_predict(series, forecast_periods)

    def _auto_select_params(self, series: pd.Series) -> tuple:
        """自动选择最优参数（网格搜索 AIC）"""
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError:
            return (1, 1, 1), (1, 1, 1, 12)

        best_aic = float("inf")
        best_order = (1, 1, 1)
        best_seasonal = (0, 0, 0, 0)

        # 简化搜索空间
        p_range = range(0, min(self.config.max_p + 1, 3))
        q_range = range(0, min(self.config.max_q + 1, 3))

        for p in p_range:
            for q in q_range:
                try:
                    order = (p, 1, q)
                    if self.config.seasonal:
                        seasonal = (1, 1, 1, self.config.seasonal_period)
                    else:
                        seasonal = (0, 0, 0, 0)

                    model = SARIMAX(
                        series, order=order, seasonal_order=seasonal,
                        enforce_stationarity=False, enforce_invertibility=False,
                    )
                    fitted = model.fit(disp=False, maxiter=100)

                    if fitted.aic < best_aic:
                        best_aic = fitted.aic
                        best_order = order
                        best_seasonal = seasonal

                except Exception:
                    continue

        logger.debug(f"ARIMA 最优参数: {best_order}x{best_seasonal}, AIC={best_aic:.1f}")
        return best_order, best_seasonal

    def _fallback_predict(self, series: pd.Series, periods: int) -> pd.Series:
        """回退预测：使用最近 3 个月均值"""
        recent = series.tail(3)
        mean_val = recent.mean()
        last_date = series.index[-1]
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq="MS")[1:]
        return pd.Series([mean_val] * periods, index=future_dates)

    def get_diagnostics(self) -> dict | None:
        """获取模型诊断信息"""
        if self._fitted is None:
            return None
        return {
            "order": self._best_order,
            "seasonal_order": self._best_seasonal_order,
            "aic": self._fitted.aic,
            "bic": self._fitted.bic,
            "params": dict(self._fitted.params),
        }

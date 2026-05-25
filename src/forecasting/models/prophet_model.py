"""Facebook Prophet 模型封装

Prophet 擅长处理：
- 强季节性数据
- 大促脉冲
- 节假日效应
- 缺失数据
"""

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ProphetConfig:
    """Prophet 配置"""
    yearly_seasonality: bool = True
    weekly_seasonality: bool = False  # 月度预测不需要
    daily_seasonality: bool = False
    changepoint_prior_scale: float = 0.05  # 趋势变化灵活度
    seasonality_prior_scale: float = 10.0  # 季节性灵活度
    seasonality_mode: str = "multiplicative"  # 乘法季节性（鞋服推荐）
    growth: str = "linear"  # linear | logistic
    include_promotions: bool = True  # 是否添加大促节假日
    include_chinese_holidays: bool = True


# 中国零售节假日
RETAIL_HOLIDAYS = pd.DataFrame({
    "holiday": ["春节", "春节", "春节", "五一", "十一", "十一", "618", "双11", "双12", "38节"],
    "ds": pd.to_datetime([
        "2025-01-28", "2026-02-17", "2027-02-06",
        "2025-05-01", "2025-10-01", "2025-10-02",
        "2025-06-18", "2025-11-11", "2025-12-12", "2025-03-08",
    ]),
    "lower_window": [-7, -7, -7, -3, -3, -3, -10, -10, -5, -3],
    "upper_window": [15, 15, 15, 5, 7, 7, 10, 5, 3, 3],
})


class ProphetModel:
    """Prophet 时间序列预测模型

    使用方式：
        model = ProphetModel()
        forecast = model.fit_predict(train_series, forecast_periods=3)
    """

    name = "Prophet"

    def __init__(self, config: ProphetConfig | None = None):
        self.config = config or ProphetConfig()
        self._model = None
        self._fitted = None

    def fit_predict(
        self,
        train_series: pd.Series,
        forecast_periods: int = 3,
    ) -> pd.Series:
        """拟合并预测

        Args:
            train_series: 训练数据（月度序列，index 为 datetime）
            forecast_periods: 预测月数

        Returns:
            预测序列
        """
        try:
            from prophet import Prophet
        except ImportError:
            logger.error("prophet 未安装，无法使用 Prophet 模型")
            return self._fallback_predict(train_series, forecast_periods)

        # 准备数据（Prophet 要求列名 ds, y）
        df = pd.DataFrame({
            "ds": train_series.index,
            "y": train_series.values,
        })
        df = df.dropna(subset=["y"])
        df["y"] = df["y"].clip(lower=0.01)  # Prophet 不支持 0 值

        if len(df) < 6:
            logger.warning("数据不足 6 个月，使用简单均值预测")
            return self._fallback_predict(train_series, forecast_periods)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                model = Prophet(
                    yearly_seasonality=self.config.yearly_seasonality,
                    weekly_seasonality=self.config.weekly_seasonality,
                    daily_seasonality=self.config.daily_seasonality,
                    changepoint_prior_scale=self.config.changepoint_prior_scale,
                    seasonality_prior_scale=self.config.seasonality_prior_scale,
                    seasonality_mode=self.config.seasonality_mode,
                    growth=self.config.growth,
                )

                # 添加中国零售节假日
                if self.config.include_chinese_holidays:
                    model.add_country_holidays(country_name="CN")
                if self.config.include_promotions:
                    model.holidays = RETAIL_HOLIDAYS

                model.fit(df)

            # 生成未来日期
            last_date = df["ds"].iloc[-1]
            future_dates = pd.date_range(
                start=last_date, periods=forecast_periods + 1, freq="MS"
            )[1:]
            future = pd.DataFrame({"ds": future_dates})

            # 预测
            forecast = model.predict(future)
            predicted = forecast["yhat"].clip(lower=0)
            predicted.index = future_dates

            self._model = model
            self._fitted = forecast

            logger.info(
                f"Prophet 拟合完成, 预测{forecast_periods}个月, "
                f"均值={predicted.mean():,.0f}"
            )

            return predicted

        except Exception as e:
            logger.warning(f"Prophet 拟合失败: {e}，回退到简单方法")
            return self._fallback_predict(train_series, forecast_periods)

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

    def get_components(self) -> pd.DataFrame | None:
        """获取预测分量（趋势、季节性、节假日）"""
        return self._fitted if self._fitted is not None else None

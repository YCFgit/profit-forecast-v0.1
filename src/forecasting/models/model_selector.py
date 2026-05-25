"""自动模型选择器

对每家门店自动跑 ARIMA + Prophet + 指数平滑，
通过回测 MAPE 选出最优模型或做集成预测。
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.forecasting.evaluation.accuracy_metrics import AccuracyResult, evaluate
from src.forecasting.models.arima_model import ARIMAModel
from src.forecasting.models.ensemble_model import EnsembleModel
from src.forecasting.models.exponential_smoothing import ExponentialSmoothingModel
from src.forecasting.models.prophet_model import ProphetModel


@dataclass
class ModelSelectionResult:
    """模型选择结果"""
    store_code: str
    best_model: str                  # 最优模型名
    best_mape: float                 # 最优 MAPE
    model_scores: dict[str, float]   # 各模型 MAPE
    forecast: pd.Series              # 最终预测结果
    model_forecasts: dict[str, pd.Series]  # 各模型预测
    ensemble_forecast: pd.Series | None = None  # 集成预测


class ModelSelector:
    """自动模型选择器

    流程：
    1. 对训练数据做 train/test split
    2. 各模型在 train 上拟合，在 test 上评估
    3. 选 MAPE 最低的模型（或做集成）

    使用方式：
        selector = ModelSelector()
        result = selector.select_and_predict(
            store_code="ST0001",
            monthly_series=series,
            forecast_periods=3,
        )
    """

    def __init__(
        self,
        test_months: int = 3,          # 回测保留月数
        use_ensemble: bool = True,      # 是否使用集成
        ensemble_method: str = "inverse_mape",
    ):
        self.test_months = test_months
        self.use_ensemble = use_ensemble
        self.ensemble_method = ensemble_method

        # 可用模型
        self.models = {
            "ARIMA": ARIMAModel(),
            "Prophet": ProphetModel(),
            "ExpSmoothing": ExponentialSmoothingModel(),
        }

    def select_and_predict(
        self,
        store_code: str,
        monthly_series: pd.Series,
        forecast_periods: int = 3,
    ) -> ModelSelectionResult:
        """选择最优模型并预测

        Args:
            store_code: 门店编码
            monthly_series: 月度销售额序列
            forecast_periods: 预测月数

        Returns:
            ModelSelectionResult
        """
        clean_series = monthly_series.dropna()

        if len(clean_series) < 6:
            logger.warning(f"[{store_code}] 数据不足，使用简单均值")
            return self._simple_forecast(store_code, clean_series, forecast_periods)

        # Train/Test split
        if len(clean_series) >= self.test_months + 3:
            split_point = len(clean_series) - self.test_months
            train = clean_series.iloc[:split_point]
            test = clean_series.iloc[split_point:]
        else:
            # 数据太少，不做回测，直接用全部数据训练
            train = clean_series
            test = None

        # 各模型预测
        model_forecasts = {}
        model_mapes = {}

        for name, model in self.models.items():
            try:
                # 在训练集上拟合并预测
                pred = model.fit_predict(train, forecast_periods=len(test) if test is not None else forecast_periods)
                model_forecasts[name] = pred

                # 回测评估
                if test is not None and len(pred) >= len(test):
                    pred_aligned = pred.iloc[:len(test)]
                    acc = evaluate(test.values, pred_aligned.values)
                    model_mapes[name] = acc.mape
                    logger.info(f"[{store_code}] {name} 回测 MAPE={acc.mape:.2%}")
                else:
                    model_mapes[name] = 0.25  # 默认值

            except Exception as e:
                logger.warning(f"[{store_code}] {name} 失败: {e}")

        if not model_forecasts:
            logger.error(f"[{store_code}] 所有模型均失败")
            return self._simple_forecast(store_code, clean_series, forecast_periods)

        # 选择最优模型
        best_model = min(model_mapes, key=model_mapes.get)
        best_mape = model_mapes[best_model]

        # 集成预测
        ensemble_forecast = None
        if self.use_ensemble and len(model_forecasts) > 1:
            ensemble = EnsembleModel(method=self.ensemble_method)
            # 用最终数据重新训练各模型
            final_forecasts = {}
            for name, model in self.models.items():
                try:
                    final_forecasts[name] = model.fit_predict(clean_series, forecast_periods)
                except Exception:
                    pass

            if final_forecasts:
                ensemble_forecast = ensemble.predict(final_forecasts, model_mapes)

        # 最终预测（集成或最优模型）
        if ensemble_forecast is not None:
            final_forecast = ensemble_forecast
            final_model = "Ensemble"
        else:
            final_forecast = model_forecasts[best_model]
            final_model = best_model

        return ModelSelectionResult(
            store_code=store_code,
            best_model=final_model,
            best_mape=best_mape,
            model_scores=model_mapes,
            forecast=final_forecast,
            model_forecasts=model_forecasts,
            ensemble_forecast=ensemble_forecast,
        )

    def _simple_forecast(
        self, store_code: str, series: pd.Series, periods: int
    ) -> ModelSelectionResult:
        """简单均值预测（数据不足时回退）"""
        clean = series.dropna()
        if len(clean) == 0:
            mean_val = 0.0
        else:
            mean_val = clean.tail(3).mean()

        last_date = clean.index[-1] if len(clean) > 0 else pd.Timestamp.now()
        future_dates = pd.date_range(start=last_date, periods=periods + 1, freq="MS")[1:]
        forecast = pd.Series([mean_val] * periods, index=future_dates)

        return ModelSelectionResult(
            store_code=store_code,
            best_model="SimpleMean",
            best_mape=0.0,
            model_scores={"SimpleMean": 0.0},
            forecast=forecast,
            model_forecasts={"SimpleMean": forecast},
        )

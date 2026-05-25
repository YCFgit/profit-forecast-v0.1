"""基线预估模块单元测试

注：TestModels / TestModelSelector 测试的是已废弃的 v1 统计模型，
保留供回测对比参考。新功能请使用 src.forecasting.rules.BaselineEngine。
"""

import pandas as pd
import pytest
import numpy as np

from src.forecasting.baseline.outlier_detector import OutlierDetector
from src.forecasting.baseline.seasonal_decompose import SeasonalDecomposer, get_shoe_seasonal_default
from src.forecasting.evaluation.accuracy_metrics import calc_mape, calc_rmse, calc_mae, calc_r2, evaluate


class TestOutlierDetector:
    """异常值检测测试"""

    def test_detect_normal_data(self):
        """正常数据应无异常值"""
        detector = OutlierDetector()
        dates = pd.date_range("2024-01-01", periods=10, freq="MS")
        data = pd.Series([100, 102, 98, 101, 99, 103, 97, 100, 101, 99], index=dates)
        clean, result = detector.detect(data)
        assert len(clean) == len(data)
        assert result.outlier_count == 0

    def test_detect_obvious_outlier(self):
        """明显异常值应被检测"""
        detector = OutlierDetector()
        dates = pd.date_range("2024-01-01", periods=10, freq="MS")
        data = pd.Series([100, 102, 98, 101, 99, 103, 97, 100, 101, 500], index=dates)
        clean, result = detector.detect(data)
        assert result.outlier_count > 0

    def test_detect_empty_series(self):
        """空序列应正常处理"""
        detector = OutlierDetector()
        data = pd.Series([], dtype=float)
        clean, result = detector.detect(data)
        assert len(clean) == 0


class TestSeasonalDecomposer:
    """季节性分解测试"""

    def test_shoe_seasonal_default(self):
        """鞋服行业默认季节因子"""
        factors = get_shoe_seasonal_default()
        assert len(factors) == 12
        # Q4 应该是旺季
        assert factors[11] > factors[1]  # 12月 > 2月

    def test_decompose_monthly_data(self):
        """月度数据分解"""
        decomposer = SeasonalDecomposer()
        # 生成 24 个月带季节性的数据
        np.random.seed(42)
        months = pd.date_range("2023-01", periods=24, freq="MS")
        seasonal = [1.0, 0.8, 0.9, 1.0, 1.1, 1.0, 0.9, 0.8, 1.0, 1.1, 1.2, 1.3] * 2
        values = [1000 * s + np.random.normal(0, 50) for s in seasonal]
        series = pd.Series(values, index=months)

        result = decomposer.decompose(series)
        assert result.strength >= 0
        assert len(result.seasonal_index) == 12


class TestAccuracyMetrics:
    """精度指标测试"""

    def test_mape_perfect(self):
        """完美预测 MAPE=0"""
        actual = np.array([100, 200, 300])
        predicted = np.array([100, 200, 300])
        assert calc_mape(actual, predicted) == 0.0

    def test_mape_known_value(self):
        """已知 MAPE 值"""
        actual = np.array([100, 200])
        predicted = np.array([110, 180])
        # MAPE = (10/100 + 20/200) / 2 = (0.1 + 0.1) / 2 = 0.1
        mape = calc_mape(actual, predicted)
        assert abs(mape - 0.1) < 1e-6

    def test_rmse(self):
        """RMSE 计算"""
        actual = np.array([100, 200])
        predicted = np.array([110, 190])
        rmse = calc_rmse(actual, predicted)
        assert rmse > 0

    def test_r2_perfect(self):
        """完美预测 R²=1"""
        actual = np.array([100, 200, 300])
        predicted = np.array([100, 200, 300])
        assert abs(calc_r2(actual, predicted) - 1.0) < 1e-6

    def test_evaluate(self):
        """综合评估"""
        actual = np.array([100, 200, 300, 400, 500])
        predicted = np.array([105, 195, 305, 395, 505])
        result = evaluate(actual, predicted)
        assert result.mape < 0.1
        assert result.r2 > 0.9


@pytest.mark.legacy
class TestModels:
    """预测模型测试（v1 废弃模型，保留供回测对比）"""

    def _make_series(self, n=12):
        """生成测试时间序列"""
        np.random.seed(42)
        dates = pd.date_range("2023-01", periods=n, freq="MS")
        values = [1000 + i * 50 + np.random.normal(0, 30) for i in range(n)]
        return pd.Series(values, index=dates)

    def test_arima_model(self):
        """ARIMA 模型预测"""
        from src.forecasting.models.arima_model import ARIMAModel
        model = ARIMAModel()
        series = self._make_series()
        pred = model.fit_predict(series, forecast_periods=3)
        assert len(pred) == 3
        assert (pred > 0).all()

    def test_exponential_smoothing(self):
        """指数平滑模型预测"""
        from src.forecasting.models.exponential_smoothing import ExponentialSmoothingModel
        model = ExponentialSmoothingModel()
        series = self._make_series()
        pred = model.fit_predict(series, forecast_periods=3)
        assert len(pred) == 3
        assert (pred > 0).all()

    def test_ensemble_model(self):
        """集成模型预测"""
        from src.forecasting.models.arima_model import ARIMAModel
        from src.forecasting.models.exponential_smoothing import ExponentialSmoothingModel
        from src.forecasting.models.ensemble_model import EnsembleModel

        ensemble = EnsembleModel()
        series = self._make_series()

        arima = ARIMAModel()
        es = ExponentialSmoothingModel()

        forecasts = {
            "ARIMA": arima.fit_predict(series, 3),
            "ExpSmoothing": es.fit_predict(series, 3),
        }
        mapes = {"ARIMA": 0.15, "ExpSmoothing": 0.10}

        pred = ensemble.predict(forecasts, mapes)
        assert len(pred) == 3


@pytest.mark.legacy
class TestModelSelector:
    """模型选择器测试（v1 废弃，保留供回测对比）"""

    def test_select_with_enough_data(self):
        """充足数据自动选模型"""
        from src.forecasting.models.model_selector import ModelSelector
        selector = ModelSelector()
        np.random.seed(42)
        dates = pd.date_range("2022-01", periods=24, freq="MS")
        values = [1000 + i * 30 + np.random.normal(0, 50) for i in range(24)]
        series = pd.Series(values, index=dates)

        result = selector.select_and_predict("TEST", series, forecast_periods=3)
        assert result.best_model is not None
        assert len(result.forecast) == 3
        assert result.best_mape >= 0

    def test_select_with_little_data(self):
        """数据不足时回退到简单均值"""
        from src.forecasting.models.model_selector import ModelSelector
        selector = ModelSelector()
        dates = pd.date_range("2024-01", periods=3, freq="MS")
        series = pd.Series([100, 200, 300], index=dates)

        result = selector.select_and_predict("TEST", series, forecast_periods=3)
        assert result.best_model == "SimpleMean"
        assert len(result.forecast) == 3

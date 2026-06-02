"""折扣率预测器（新 11 方法版）单元测试"""

import pytest
from src.discount.discount_predictor import (
    DiscountPredictor,
    DiscountPrediction,
    METHODS,
    SPRING_MONTHS,
    SEASONAL_CLIP_LOW,
    SEASONAL_CLIP_HIGH,
    DISC_RATE_LOW,
    DISC_RATE_HIGH,
)


@pytest.fixture
def predictor():
    return DiscountPredictor()


@pytest.fixture
def sample_history():
    """12 个月历史数据（降序）"""
    return [
        (202605, 0.725), (202604, 0.700), (202603, 0.710),
        (202602, 0.680), (202601, 0.690), (202512, 0.670),
        (202511, 0.660), (202510, 0.650), (202509, 0.640),
        (202508, 0.630), (202507, 0.620), (202506, 0.730),
    ]


class TestDiscountPredictor:

    def test_predict_returns_valid_result(self, predictor, sample_history):
        """预测返回有效结果"""
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=sample_history,
        )
        assert isinstance(result, DiscountPrediction)
        assert result.brand == "NK"
        assert result.region == "华东"
        assert DISC_RATE_LOW <= result.predicted_rate <= DISC_RATE_HIGH

    def test_predict_with_method_count(self, predictor, sample_history):
        """应有多个有效方法"""
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=sample_history,
        )
        valid = [v for v in result.all_predictions.values() if v is not None]
        assert len(valid) >= 4

    def test_spring_month_excluded(self, predictor):
        """春节月应被排除"""
        # 202602 是春节月
        history = [
            (202605, 0.70), (202604, 0.69), (202603, 0.68),
            (202602, 0.999),  # 春节月，应被忽略
            (202601, 0.67), (202512, 0.66),
        ]
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=history,
        )
        # 999 不应影响预测
        assert result.predicted_rate < 0.90

    def test_recent_avg_method(self, predictor, sample_history):
        """近期均值方法"""
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=sample_history,
            best_method="近期均值(3月)",
        )
        # 近3个非春节月: 202605=0.725, 202604=0.700, 202603=0.710
        expected = (0.725 + 0.700 + 0.710) / 3
        assert abs(result.predicted_rate - expected) < 0.01

    def test_fixed_value_method(self, predictor):
        """固定值方法 — 波动小时用均值"""
        # 低波动历史
        history = [(202600 + i, 70.0 + i * 0.1) for i in range(5, 0, -1)]
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=history,
            best_method="固定值",
        )
        assert result.predicted_rate is not None

    def test_empty_history_fallback(self, predictor):
        """空历史应返回默认值"""
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=[],
        )
        assert result.predicted_rate >= DISC_RATE_LOW

    def test_yoy_method(self, predictor, sample_history):
        """同比推算方法"""
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=sample_history,
            best_method="同比推算",
        )
        assert result.predicted_rate is not None
        assert DISC_RATE_LOW <= result.predicted_rate <= DISC_RATE_HIGH

    def test_blend_method(self, predictor, sample_history):
        """区域全国混合方法"""
        national = [(202605, 73.0), (202604, 71.0), (202603, 72.0),
                     (202601, 69.0), (202512, 68.0)]
        result = predictor.predict(
            brand="NK", region="华东",
            target_month="2026-06",
            history=sample_history,
            national_history=national,
            best_method="区域全国混合",
        )
        assert result.predicted_rate is not None

    def test_all_methods_defined(self):
        """11种方法完整性"""
        assert len(METHODS) == 11
        assert "固定值" in METHODS
        assert "近期均值(3月)" in METHODS
        assert "季节修正(3月)" in METHODS
        assert "同比推算" in METHODS
        assert "区域全国混合" in METHODS

    def test_seasonal_factor_clamped(self, predictor):
        """季节因子截断到 [0.7, 1.3]"""
        assert SEASONAL_CLIP_LOW == 0.70
        assert SEASONAL_CLIP_HIGH == 1.30

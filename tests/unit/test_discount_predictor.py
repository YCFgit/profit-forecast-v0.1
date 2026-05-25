import pytest
import pandas as pd
from src.forecasting.discount.brand_season_matrix import BrandSeasonMatrix
from src.forecasting.discount.predictor import DiscountPredictor


@pytest.fixture
def sample_pos_data():
    """模拟 POS 数据"""
    records = []
    for month in range(1, 13):
        for brand in ["NK", "AD"]:
            for season in ["当季", "上季", "旧款"]:
                for i in range(10):
                    discount = {"当季": 0.95, "上季": 0.75, "旧款": 0.50}[season]
                    records.append({
                        "brand_code": brand,
                        "brand_name": brand,
                        "season_type": season,
                        "months_since_launch": month,
                        "year_month": f"2025{month:02d}",
                        "discount_rate": discount + (i - 5) * 0.01,
                    })
    return pd.DataFrame(records)


def test_brand_season_matrix_builds_correctly(sample_pos_data):
    """测试品牌季节折扣矩阵构建"""
    matrix = BrandSeasonMatrix(sample_pos_data)
    result = matrix.get_matrix()

    assert not result.empty
    assert "avg_discount_rate" in result.columns
    # 当季折扣应高于旧款
    current_season = result[result["season_type"] == "当季"]["avg_discount_rate"].mean()
    old_season = result[result["season_type"] == "旧款"]["avg_discount_rate"].mean()
    assert current_season > old_season


def test_predictor_returns_forecast(sample_pos_data):
    """测试折扣预测器返回预测结果"""
    predictor = DiscountPredictor(sample_pos_data)
    forecast = predictor.predict(brand_code="NK", months_ahead=3)

    assert len(forecast) == 3
    assert "month_offset" in forecast.columns
    assert "forecast_discount_rate" in forecast.columns
    assert all(0 < r <= 1 for r in forecast["forecast_discount_rate"])

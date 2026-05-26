import pytest
import pandas as pd
from src.risk.risk_assessor import RiskAssessor


@pytest.fixture
def sales_history():
    """模拟历史销售数据"""
    dates = pd.date_range("2025-01-01", periods=365, freq="D")
    import numpy as np
    np.random.seed(42)
    values = 50000 + np.random.normal(0, 5000, 365)
    return pd.DataFrame({
        "store_no": "S001",
        "base_date": dates.strftime("%Y%m%d"),
        "revenue": values,
    })


def test_assess_risk_returns_probability(sales_history):
    """测试风险评估返回达标概率"""
    assessor = RiskAssessor()
    result = assessor.assess_store_risk(
        store_no="S001",
        target=1500000,  # 月目标
        sales_history=sales_history,
    )

    assert "reachability_prob" in result
    assert "risk_level" in result
    assert 0 <= result["reachability_prob"] <= 1


def test_risk_level_classification(sales_history):
    """测试风险等级分类"""
    assessor = RiskAssessor()

    # 低目标 → 低风险
    low_result = assessor.assess_store_risk(
        store_no="S001", target=100000, sales_history=sales_history,
    )
    assert low_result["risk_level"] in ["low", "medium"]

    # 高目标 → 高风险
    high_result = assessor.assess_store_risk(
        store_no="S001", target=5000000, sales_history=sales_history,
    )
    assert high_result["risk_level"] in ["high", "critical"]

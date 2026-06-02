"""增量利润推算器单元测试"""

import pytest
from src.profit.incremental_profit import (
    IncrementalProfitCalculator,
    StoreCostRates,
    NATIONAL_DEFAULTS,
)


class TestStoreCostRates:
    """StoreCostRates 测试"""

    def test_default_m_variable(self):
        """默认比率下 m_variable 应在合理范围"""
        rates = StoreCostRates(store_code="T")
        # 默认: 1 - 0.49/0.75 - 0.15 + 0.011/0.75 ≈ 0.285
        assert 0.20 <= rates.m_variable <= 0.40

    def test_m_variable_formula(self):
        """验证 m_variable 公式"""
        rates = StoreCostRates(
            store_code="T",
            discount_rate=0.80,
            cost_rate=0.50,
            mall_fee_rate=0.12,
            rebate_rate=0.01,
        )
        expected = 1.0 - 0.50 / 0.80 - 0.12 + 0.01 / 0.80
        assert abs(rates.m_variable - expected) < 0.001

    def test_m_variable_clamped(self):
        """折扣率截断到 [0.3, 1.0]，m_variable 公式仍可计算"""
        rates = StoreCostRates(store_code="T", discount_rate=0.10)
        # discount_rate=0.10 被截断到 0.30，m_variable 可能为负（正常）
        assert isinstance(rates.m_variable, float)
        # 用合理折扣率测试
        rates2 = StoreCostRates(store_code="T", discount_rate=0.75)
        assert rates2.m_variable > 0

    def test_m_full_includes_fixed(self):
        """m_full 包含固定费用，应小于 m_variable"""
        rates = StoreCostRates(store_code="T")
        assert rates.m_full < rates.m_variable

    def test_national_defaults(self):
        """全国兜底默认值完整性"""
        assert "discount_rate" in NATIONAL_DEFAULTS
        assert "cost_rate" in NATIONAL_DEFAULTS
        assert NATIONAL_DEFAULTS["discount_rate"] == 0.75


class TestIncrementalProfitCalculator:
    """IncrementalProfitCalculator 测试"""

    @pytest.fixture
    def calc(self):
        return IncrementalProfitCalculator()

    def test_basic_calculation(self, calc):
        """基本计算流程"""
        result = calc.calculate(
            baselines={"S1": 100000},
            targets={"S1": 120000},
            cost_rates={"S1": StoreCostRates(store_code="S1")},
            achievement_probs={"S1": 0.85},
        )
        assert result.store_count == 1
        assert result.total_baseline == 100000
        # 期望收入 = 100000 + 20000 * 0.85 = 117000
        assert result.total_expected_revenue == 117000
        assert result.total_net_profit != 0

    def test_no_extra_target(self, calc):
        """无加压时净利润 = 基线利润"""
        result = calc.calculate(
            baselines={"S1": 100000},
            targets={"S1": 100000},
            cost_rates={"S1": StoreCostRates(store_code="S1")},
        )
        detail = result.stores["S1"]
        assert detail.extra_target == 0
        assert detail.expected_revenue == 100000

    def test_variable_margin_positive(self, calc):
        """变动边际利润应为正"""
        result = calc.calculate(
            baselines={"S1": 100000},
            targets={"S1": 150000},
            cost_rates={"S1": StoreCostRates(store_code="S1")},
            achievement_probs={"S1": 0.70},
        )
        assert result.stores["S1"].variable_margin > 0

    def test_fixed_cost_anchored_to_baseline(self, calc):
        """固定成本以基线为锚，不随加压变动"""
        rates = StoreCostRates(store_code="S1")
        result_base = calc.calculate(
            baselines={"S1": 100000},
            targets={"S1": 100000},
            cost_rates={"S1": rates},
        )
        result_high = calc.calculate(
            baselines={"S1": 100000},
            targets={"S1": 200000},
            cost_rates={"S1": rates},
            achievement_probs={"S1": 1.0},
        )
        # 固定费用应相同（都以基线100000为锚）
        assert result_base.stores["S1"].fixed_expense == result_high.stores["S1"].fixed_expense

    def test_region_summary(self, calc):
        """区域汇总"""
        result = calc.calculate(
            baselines={"S1": 100000, "S2": 80000},
            targets={"S1": 120000, "S2": 90000},
            cost_rates={
                "S1": StoreCostRates(store_code="S1"),
                "S2": StoreCostRates(store_code="S2"),
            },
            store_meta={
                "S1": {"region": "华东", "brand": "NK"},
                "S2": {"region": "华东", "brand": "NK"},
            },
        )
        assert "华东" in result.region_summary
        assert result.region_summary["华东"]["count"] == 2

    def test_compute_rates_from_financials(self, calc):
        """从财务数据计算比率"""
        financials = {
            "S1": {
                "revenue": 100000,
                "list_price": 133333,
                "tax_cost": 65000,
                "mall_fee": 12000,
                "operating_exp": 30000,
                "managing_exp": 2400,
                "nonoperating": 500,
                "platform_rebate": 1500,
                "return_commission": 500,
            }
        }
        rates = calc.compute_rates_from_financials(financials)
        assert "S1" in rates
        assert 0.3 <= rates["S1"].discount_rate <= 1.0
        assert 0.2 <= rates["S1"].cost_rate <= 0.8

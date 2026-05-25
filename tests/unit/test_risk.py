"""风险评估模块单元测试"""

import numpy as np
import pandas as pd
import pytest

from src.risk.reachability import ReachabilityAssessor, ReachabilityResult
from src.risk.pressure_distribution import PressureDistributionAnalyzer
from src.risk.scenario_modeler import MonteCarloSimulator, MonteCarloResult
from src.risk.risk_assessor import RiskAssessor, RiskFactor, RiskAssessment
from src.risk.risk_report import RiskReportGenerator


class TestReachabilityAssessor:
    """目标可达性评估测试"""

    def test_assess_low_risk(self):
        """低风险目标"""
        assessor = ReachabilityAssessor()
        targets = {"ST0001": 110_000}
        baselines = {"ST0001": 100_000}
        results = assessor.assess(targets, baselines)

        assert len(results) == 1
        assert results[0].risk_level == "low"
        assert results[0].target_ratio == pytest.approx(1.1)

    def test_assess_high_risk(self):
        """高风险目标"""
        assessor = ReachabilityAssessor()
        targets = {"ST0001": 250_000}
        baselines = {"ST0001": 100_000}
        results = assessor.assess(targets, baselines)

        assert len(results) == 1
        assert results[0].risk_level in ("high", "critical")

    def test_assess_multiple_stores(self):
        """多门店评估"""
        assessor = ReachabilityAssessor()
        targets = {f"ST{i:04d}": 100_000 + i * 20_000 for i in range(1, 6)}
        baselines = {f"ST{i:04d}": 100_000 for i in range(1, 6)}
        results = assessor.assess(targets, baselines)

        assert len(results) == 5
        # 应按风险分数降序排列
        assert results[0].risk_score >= results[-1].risk_score

    def test_to_dataframe(self):
        """转 DataFrame"""
        assessor = ReachabilityAssessor()
        targets = {"ST0001": 110_000}
        baselines = {"ST0001": 100_000}
        results = assessor.assess(targets, baselines)
        df = assessor.to_dataframe(results)

        assert len(df) == 1
        assert "门店编码" in df.columns
        assert "风险等级" in df.columns


class TestPressureDistributionAnalyzer:
    """承压分布分析测试"""

    def test_analyze(self, allocation_plan):
        """承压分布分析"""
        analyzer = PressureDistributionAnalyzer()
        result = analyzer.analyze(allocation_plan)

        assert result.mean_pressure_rate > 0
        assert result.std_pressure_rate >= 0
        assert result.p25 <= result.p75
        assert len(result.histogram) > 0

    def test_analyze_empty(self):
        """空分配方案"""
        from src.allocation.target_allocator import AllocationPlan
        analyzer = PressureDistributionAnalyzer()
        plan = AllocationPlan(
            allocations={}, total_target=0,
            total_baseline=0, total_gap=0, store_count=0,
        )
        result = analyzer.analyze(plan)

        assert result.mean_pressure_rate == 0
        assert result.std_pressure_rate == 0


class TestMonteCarloSimulator:
    """蒙特卡洛模拟测试"""

    def test_simulate_basic(self):
        """基本模拟"""
        simulator = MonteCarloSimulator()
        result = simulator.simulate(
            base_revenue=1_000_000,
            base_cost=700_000,
            n_simulations=1000,
        )

        assert result.n_simulations == 1000
        assert result.profit_mean > 0
        assert result.profit_std > 0
        assert 0 <= result.loss_probability <= 1

    def test_var_cvar(self):
        """VaR 和 CVaR 计算"""
        simulator = MonteCarloSimulator()
        result = simulator.simulate(
            base_revenue=1_000_000,
            base_cost=700_000,
            n_simulations=5000,
        )

        # 利润为正时 VaR95 应为 0
        assert result.var_95 >= 0
        assert result.cvar_95 >= 0

    def test_simulate_high_volatility(self):
        """高波动率应增大标准差"""
        simulator = MonteCarloSimulator()
        low_vol = simulator.simulate(1_000_000, 700_000, revenue_volatility=0.05, n_simulations=2000)
        high_vol = simulator.simulate(1_000_000, 700_000, revenue_volatility=0.30, n_simulations=2000)

        assert high_vol.profit_std > low_vol.profit_std

    def test_simulate_stores(self):
        """逐门店模拟"""
        simulator = MonteCarloSimulator()
        revenues = {"ST0001": 500_000, "ST0002": 300_000}
        costs = {"ST0001": 350_000, "ST0002": 210_000}
        results = simulator.simulate_stores(revenues, costs, n_simulations=500)

        assert len(results) == 2
        assert "ST0001" in results
        assert "ST0002" in results


class TestRiskAssessor:
    """综合风险评估测试"""

    def test_assess_basic(self, allocation_plan, profit_summary_from_plan):
        """基本风险评估"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan, profit_summary_from_plan)

        assert assessment.overall_score >= 0
        assert assessment.overall_level in ("low", "medium", "high", "critical")
        assert len(assessment.factors) > 0

    def test_assess_without_profit(self, allocation_plan):
        """无利润数据的风险评估"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan)

        # 应有 4 个风险因素（无利润不确定性）
        assert len(assessment.factors) == 4
        assert assessment.monte_carlo is None

    def test_to_dataframe(self, allocation_plan):
        """转 DataFrame"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan)
        df = assessment.to_dataframe()

        assert len(df) > 0
        assert "风险因素" in df.columns
        assert "风险分数" in df.columns


class TestRiskReportGenerator:
    """风险报告生成器测试"""

    def test_generate_summary_dict(self, allocation_plan):
        """生成汇总字典"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan)

        gen = RiskReportGenerator()
        d = gen.generate_summary_dict(assessment)

        assert "综合风险分" in d
        assert "综合风险等级" in d

    def test_generate_recommendations(self, allocation_plan):
        """生成建议列表"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan)

        gen = RiskReportGenerator()
        recs = gen.generate_recommendations(assessment)

        assert isinstance(recs, list)

    def test_generate_high_risk_stores(self, allocation_plan):
        """生成高风险门店明细"""
        assessor = RiskAssessor()
        assessment = assessor.assess(allocation_plan)

        gen = RiskReportGenerator()
        df = gen.generate_high_risk_stores(assessment)

        assert isinstance(df, pd.DataFrame)


# ============================================================
# 辅助 fixture
# ============================================================

@pytest.fixture
def profit_summary_from_plan(allocation_plan):
    """从分配方案生成利润汇总"""
    from src.profit.profit_calculator import ProfitCalculator
    calc = ProfitCalculator()
    targets = {c: a.target for c, a in allocation_plan.allocations.items()}
    return calc.calculate(targets)

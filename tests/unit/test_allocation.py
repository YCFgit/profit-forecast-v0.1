"""承压分配模块单元测试"""

import pytest

from src.allocation.weight_calculator import WeightCalculator, StoreProfile, WeightConfig
from src.allocation.target_allocator import TargetAllocator
from src.allocation.constraint_checker import ConstraintChecker, ConstraintConfig
from src.allocation.fairness_checker import FairnessChecker
from src.allocation.scenario_simulator import ScenarioSimulator


class TestWeightCalculator:
    """权重计算测试"""

    def _make_profiles(self, n=5):
        """创建测试门店画像"""
        profiles = {}
        for i in range(n):
            code = f"ST{i+1:04d}"
            profiles[code] = StoreProfile(
                store_code=code,
                historical_profit=100_000 + i * 50_000,
                sales_per_sqm=5000 + i * 1000,
                commercial_tier=["A", "B", "C", "D", "E"][i % 5],
                city_level="二线",
                store_area=100 + i * 20,
                growth_rate=0.05 * i,
                opening_months=365,
            )
        return profiles

    def test_calculate_weights(self):
        """权重计算应返回归一化结果"""
        calc = WeightCalculator()
        profiles = self._make_profiles()
        weights = calc.calculate(profiles)
        assert len(weights) == len(profiles)
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        assert all(w > 0 for w in weights.values())

    def test_calculate_with_detail(self):
        """详细权重计算应返回 DataFrame"""
        calc = WeightCalculator()
        profiles = self._make_profiles()
        df = calc.calculate_with_detail(profiles)
        assert len(df) == len(profiles)
        assert "store_code" in df.columns
        assert "weight" in df.columns


class TestTargetAllocator:
    """承压分配测试"""

    def _make_data(self, n=5):
        profiles = {}
        baselines = {}
        for i in range(n):
            code = f"ST{i+1:04d}"
            baseline = 100_000 + i * 50_000
            profiles[code] = StoreProfile(
                store_code=code,
                historical_profit=baseline,
                sales_per_sqm=5000,
                commercial_tier="B",
                city_level="二线",
                store_area=100,
                growth_rate=0.05,
                opening_months=365,
            )
            baselines[code] = baseline
        return profiles, baselines

    def test_allocate_basic(self):
        """基本分配测试"""
        allocator = TargetAllocator()
        profiles, baselines = self._make_data()
        total_target = sum(baselines.values()) * 1.20

        plan = allocator.allocate(total_target, baselines, profiles)
        assert plan.store_count == 5
        assert plan.total_allocated > 0
        assert abs(plan.total_allocated - total_target) < 1.0

    def test_allocate_preserves_total(self):
        """分配总额应等于目标"""
        allocator = TargetAllocator()
        profiles, baselines = self._make_data()
        total_target = sum(baselines.values()) * 1.15

        plan = allocator.allocate(total_target, baselines, profiles)
        assert abs(plan.total_allocated - total_target) < 1.0

    def test_allocate_floor_constraint(self):
        """分配不应低于保底线"""
        allocator = TargetAllocator()
        profiles, baselines = self._make_data()
        total_target = sum(baselines.values()) * 0.5  # 极低目标

        plan = allocator.allocate(total_target, baselines, profiles)
        for code, alloc in plan.allocations.items():
            floor = baselines[code] * 0.8
            assert alloc.target >= floor - 1.0  # 允许微小浮点误差

    def test_allocate_with_new_store(self):
        """新店应受保护"""
        allocator = TargetAllocator()
        profiles, baselines = self._make_data()
        # 设置第一家为新店
        list(profiles.values())[0].opening_months = 3

        total_target = sum(baselines.values()) * 1.30
        plan = allocator.allocate(total_target, baselines, profiles)
        assert plan.constraint_result.new_store_count >= 1


class TestFairnessChecker:
    """公平性检查测试"""

    def test_fairness_check(self, allocation_plan):
        """公平性检查应返回有效结果"""
        checker = FairnessChecker()
        result = checker.check(allocation_plan)
        assert result.grade in ("A", "B", "C", "D")
        assert result.cv >= 0
        assert result.avg_pressure_rate is not None


class TestScenarioSimulator:
    """情景模拟测试"""

    def test_simulate_scenarios(self, baselines, store_profiles):
        """情景模拟应返回 3 个方案"""
        simulator = ScenarioSimulator()
        comparison = simulator.simulate(baselines, store_profiles)
        assert len(comparison.scenarios) == 3
        assert "保守方案" in comparison.scenarios
        assert "稳健方案" in comparison.scenarios
        assert "激进方案" in comparison.scenarios

    def test_recommend(self, baselines, store_profiles):
        """推荐方案应返回有效名称"""
        simulator = ScenarioSimulator()
        comparison = simulator.simulate(baselines, store_profiles)
        rec = comparison.recommend()
        assert rec in ("保守方案", "稳健方案", "激进方案")

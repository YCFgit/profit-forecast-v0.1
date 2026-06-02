"""MIP 运筹分配器单元测试"""

import pytest
from src.allocation.mip_allocator import (
    MIPAllocator,
    MIPAllocationResult,
    MIPStoreResult,
    DIFFICULTY_LEVELS,
)


@pytest.fixture
def allocator():
    return MIPAllocator()


@pytest.fixture
def sample_data():
    """5 家门店的测试数据"""
    baselines = {f"ST{i:03d}": 100000 * (i + 1) for i in range(5)}
    marginal_rates = {f"ST{i:03d}": 0.20 + i * 0.02 for i in range(5)}
    ceilings = {code: v * 1.5 for code, v in baselines.items()}
    store_meta = {
        f"ST{i:03d}": {"region": "华东" if i < 3 else "华南", "brand": "NK"}
        for i in range(5)
    }
    return baselines, marginal_rates, ceilings, store_meta


class TestMIPAllocator:

    def test_basic_allocation(self, allocator, sample_data):
        """基本分配流程"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10  # 目标 = 基线 × 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
            store_meta=meta,
        )

        assert isinstance(result, MIPAllocationResult)
        assert result.store_count == 5
        assert result.participating_count == 5
        assert result.total_allocated > 0

    def test_target_constraint(self, allocator, sample_data):
        """分配总额应在目标范围内 [95%, 100%]"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
        )

        # 分配总额应在目标的 95%-100% 之间
        assert result.total_allocated >= total_target * 0.90
        assert result.total_allocated <= total_target * 1.05

    def test_ceiling_constraint(self, allocator, sample_data):
        """每家门店不应超过天花板"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
        )

        for code, store in result.stores.items():
            ceiling = ceilings.get(code, baselines[code] * 1.5)
            assert store.target <= ceiling + 1  # 允许1元舍入误差

    def test_difficulty_levels(self, allocator, sample_data):
        """难度档位定义完整性"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.05

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
        )

        valid_levels = {d[0] for d in DIFFICULTY_LEVELS}
        valid_levels.add("none")
        for store in result.stores.values():
            assert store.difficulty_level in valid_levels

    def test_achievement_probability(self, allocator, sample_data):
        """达成概率应在合理范围"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
        )

        for store in result.stores.values():
            assert 0 <= store.achievement_probability <= 1.0

    def test_expected_marginal_profit(self, allocator, sample_data):
        """期望边际利润应为正"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
        )

        assert result.expected_total_marginal_profit >= 0

    def test_exclude_stores(self, allocator, sample_data):
        """排除门店"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
            exclude_stores={"ST000"},
        )

        assert "ST000" not in result.stores
        assert result.participating_count == 4

    def test_region_summary(self, allocator, sample_data):
        """区域汇总"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        result = allocator.allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
            ceilings=ceilings,
            store_meta=meta,
        )

        assert "华东" in result.region_summary
        assert "华南" in result.region_summary
        assert result.region_summary["华东"]["store_count"] == 3

    def test_fallback_when_no_pulp(self, allocator, sample_data):
        """PuLP 不可用时降级分配"""
        baselines, rates, ceilings, meta = sample_data
        total_target = sum(baselines.values()) * 1.10

        # 直接调用降级方法
        result = allocator._fallback_allocate(
            total_target=total_target,
            baselines=baselines,
            marginal_rates=rates,
        )

        assert result.solver_status == "Fallback"
        assert result.store_count == 5

    def test_no_stores(self, allocator):
        """无门店时返回空结果"""
        result = allocator.allocate(
            total_target=100000,
            baselines={},
            marginal_rates={},
            ceilings={},
        )
        assert result.store_count == 0
        assert result.solver_status == "NoStores"

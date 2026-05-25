"""承压分配模块

老板总目标 → 按门店能力权重分配 → 约束调整 → 公平性检查 → 情景模拟

核心类：
  - TargetAllocator: 承压分配主逻辑
  - WeightCalculator: 门店能力权重计算
  - ConstraintChecker: 约束检查（保底线/上限/新店保护）
  - FairnessChecker: 公平性检查
  - ScenarioSimulator: 多情景模拟
"""

from src.allocation.constraint_checker import (
    ConstraintChecker,
    ConstraintConfig,
    ConstraintResult,
    ConstraintViolation,
)
from src.allocation.fairness_checker import FairnessChecker, FairnessResult
from src.allocation.scenario_simulator import (
    ScenarioComparison,
    ScenarioResult,
    ScenarioSimulator,
)
from src.allocation.target_allocator import (
    AllocationPlan,
    AllocationResult,
    TargetAllocator,
)
from src.allocation.weight_calculator import (
    StoreProfile,
    WeightCalculator,
    WeightConfig,
)

__all__ = [
    "TargetAllocator", "AllocationPlan", "AllocationResult",
    "WeightCalculator", "WeightConfig", "StoreProfile",
    "ConstraintChecker", "ConstraintConfig", "ConstraintResult", "ConstraintViolation",
    "FairnessChecker", "FairnessResult",
    "ScenarioSimulator", "ScenarioComparison", "ScenarioResult",
]

"""约束检查器

承压分配的约束条件：
  1. 保底线: 目标 ≥ 基线 × floor_ratio (默认 80%)
  2. 上限: 目标 ≤ 基线 × ceiling_ratio (默认 200%)
  3. 新店保护: 开业 < 6 个月，承压系数打 7 折
  4. 最低目标: 目标不能为负
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger


@dataclass
class ConstraintConfig:
    """约束配置"""
    floor_ratio: float = 0.80       # 保底线: 基线 × 80%
    ceiling_ratio: float = 2.00     # 上限: 基线 × 200%
    new_store_months: int = 6       # 新店定义: 开业 < N 个月
    new_store_factor: float = 0.70  # 新店承压系数
    min_target: float = 0.0         # 最低目标（不能为负）


@dataclass
class ConstraintViolation:
    """约束违反记录"""
    store_code: str
    violation_type: str   # floor | ceiling | new_store | negative
    original_target: float
    adjusted_target: float
    reason: str


@dataclass
class ConstraintResult:
    """约束检查结果"""
    adjusted_targets: dict[str, float]      # 调整后的目标
    violations: list[ConstraintViolation]   # 违反记录
    new_store_count: int = 0
    floor_hit_count: int = 0
    ceiling_hit_count: int = 0

    @property
    def total_violations(self) -> int:
        return len(self.violations)


class ConstraintChecker:
    """约束检查器

    使用方式：
        checker = ConstraintChecker()
        result = checker.check(targets, baselines, store_profiles)
    """

    def __init__(self, config: ConstraintConfig | None = None):
        self.config = config or ConstraintConfig()

    def check(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        store_profiles: dict | None = None,
    ) -> ConstraintResult:
        """检查并调整目标

        Args:
            targets: {门店编码: 分配目标}
            baselines: {门店编码: 基线值}
            store_profiles: {门店编码: StoreProfile}，用于新店判断

        Returns:
            ConstraintResult
        """
        adjusted = {}
        violations = []
        new_store_count = 0
        floor_hit = 0
        ceiling_hit = 0

        for store_code, target in targets.items():
            baseline = baselines.get(store_code, 0)
            original_target = target
            current_target = target

            # 新店保护
            is_new = False
            if store_profiles and store_code in store_profiles:
                profile = store_profiles[store_code]
                opening_months = getattr(profile, "opening_months", 12)
                if opening_months < self.config.new_store_months:
                    is_new = True
                    new_store_count += 1
                    # 新店目标 = 基线 + (目标 - 基线) × 新店系数
                    pressure = current_target - baseline
                    current_target = baseline + pressure * self.config.new_store_factor
                    violations.append(ConstraintViolation(
                        store_code=store_code,
                        violation_type="new_store",
                        original_target=original_target,
                        adjusted_target=current_target,
                        reason=f"新店保护(开业{opening_months}个月 < {self.config.new_store_months}个月), "
                               f"承压系数 {self.config.new_store_factor}",
                    ))

            # 保底线检查
            if baseline > 0:
                floor = baseline * self.config.floor_ratio
                if current_target < floor:
                    floor_hit += 1
                    violations.append(ConstraintViolation(
                        store_code=store_code,
                        violation_type="floor",
                        original_target=current_target,
                        adjusted_target=floor,
                        reason=f"目标 {current_target:,.0f} < 保底线 {floor:,.0f} (基线×{self.config.floor_ratio:.0%})",
                    ))
                    current_target = floor

                # 上限检查
                ceiling = baseline * self.config.ceiling_ratio
                if current_target > ceiling:
                    ceiling_hit += 1
                    violations.append(ConstraintViolation(
                        store_code=store_code,
                        violation_type="ceiling",
                        original_target=current_target,
                        adjusted_target=ceiling,
                        reason=f"目标 {current_target:,.0f} > 上限 {ceiling:,.0f} (基线×{self.config.ceiling_ratio:.0%})",
                    ))
                    current_target = ceiling

            # 最低目标
            if current_target < self.config.min_target:
                violations.append(ConstraintViolation(
                    store_code=store_code,
                    violation_type="negative",
                    original_target=current_target,
                    adjusted_target=self.config.min_target,
                    reason=f"目标 {current_target:,.0f} < 最低目标 {self.config.min_target:,.0f}",
                ))
                current_target = self.config.min_target

            adjusted[store_code] = current_target

        result = ConstraintResult(
            adjusted_targets=adjusted,
            violations=violations,
            new_store_count=new_store_count,
            floor_hit_count=floor_hit,
            ceiling_hit_count=ceiling_hit,
        )

        if violations:
            logger.info(
                f"约束调整: {len(violations)} 项调整, "
                f"新店保护={new_store_count}, 保底线触达={floor_hit}, 上限触达={ceiling_hit}"
            )

        return result

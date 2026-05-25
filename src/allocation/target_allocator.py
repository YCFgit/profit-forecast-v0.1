"""承压分配主逻辑

老板设定总利润目标 → 按门店能力权重分配 → 约束调整 → 重平衡

核心流程：
  1. 计算缺口 = 总目标 - Σ 基线
  2. 按权重分配承压额
  3. 约束检查（保底线/上限/新店保护）
  4. 因约束调整导致的差额重平衡
  5. 输出最终分配方案
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.allocation.constraint_checker import (
    ConstraintChecker,
    ConstraintConfig,
    ConstraintResult,
)
from src.allocation.weight_calculator import (
    StoreProfile,
    WeightCalculator,
    WeightConfig,
)


@dataclass
class AllocationResult:
    """单店分配结果"""
    store_code: str
    baseline: float              # 基线值
    weight: float                # 权重
    pressure: float              # 承压额（正=加压，负=减压）
    target: float                # 最终目标 = 基线 + 承压额
    growth_rate: float           # 增长率 = (目标 - 基线) / 基线
    is_new_store: bool = False
    constraint_adjusted: bool = False  # 是否被约束调整

    @property
    def pressure_ratio(self) -> float:
        """承压率 = 承压额 / 基线"""
        return self.pressure / self.baseline if self.baseline > 0 else 0


@dataclass
class AllocationPlan:
    """完整分配方案"""
    total_target: float                    # 老板总目标
    total_baseline: float                  # 总基线
    total_gap: float                       # 总缺口
    store_count: int                       # 参与分配门店数
    allocations: dict[str, AllocationResult]  # 各店分配结果
    constraint_result: ConstraintResult | None = None
    rebalance_rounds: int = 0              # 重平衡轮数

    @property
    def total_allocated(self) -> float:
        return sum(a.target for a in self.allocations.values())

    @property
    def avg_growth_rate(self) -> float:
        rates = [a.growth_rate for a in self.allocations.values()]
        return sum(rates) / len(rates) if rates else 0

    @property
    def max_growth_rate(self) -> float:
        return max(a.growth_rate for a in self.allocations.values()) if self.allocations else 0

    @property
    def min_growth_rate(self) -> float:
        return min(a.growth_rate for a in self.allocations.values()) if self.allocations else 0

    def to_dataframe(self) -> pd.DataFrame:
        """转为 DataFrame"""
        rows = []
        for code, alloc in sorted(self.allocations.items()):
            rows.append({
                "门店编码": code,
                "基线": round(alloc.baseline, 0),
                "权重": round(alloc.weight, 4),
                "承压额": round(alloc.pressure, 0),
                "目标": round(alloc.target, 0),
                "增长率": f"{alloc.growth_rate:.1%}",
                "新店": "是" if alloc.is_new_store else "否",
                "约束调整": "是" if alloc.constraint_adjusted else "否",
            })
        return pd.DataFrame(rows)


class TargetAllocator:
    """承压分配器

    使用方式：
        allocator = TargetAllocator()
        plan = allocator.allocate(
            total_target=5_000_000,
            baselines={"ST0001": 100_000, ...},
            store_profiles={"ST0001": StoreProfile(...), ...},
        )
    """

    def __init__(
        self,
        weight_config: WeightConfig | None = None,
        constraint_config: ConstraintConfig | None = None,
        max_rebalance_rounds: int = 5,
    ):
        self.weight_calc = WeightCalculator(weight_config)
        self.constraint_checker = ConstraintChecker(constraint_config)
        self.max_rebalance_rounds = max_rebalance_rounds

    def allocate(
        self,
        total_target: float,
        baselines: dict[str, float],
        store_profiles: dict[str, StoreProfile] | None = None,
    ) -> AllocationPlan:
        """执行承压分配

        Args:
            total_target: 老板设定的总利润目标
            baselines: {门店编码: 基线利润}
            store_profiles: {门店编码: 门店画像}，为空则等权分配

        Returns:
            AllocationPlan
        """
        store_codes = list(baselines.keys())
        n_stores = len(store_codes)
        total_baseline = sum(baselines.values())
        gap = total_target - total_baseline

        logger.info(
            f"承压分配开始: 总目标={total_target:,.0f}, "
            f"总基线={total_baseline:,.0f}, 缺口={gap:,.0f}, "
            f"门店数={n_stores}"
        )

        # Step 1: 计算权重
        if store_profiles:
            weights = self.weight_calc.calculate(store_profiles)
        else:
            weights = {code: 1.0 / n_stores for code in store_codes}

        # Step 2: 按权重分配承压额
        raw_targets = {}
        for code in store_codes:
            baseline = baselines[code]
            w = weights.get(code, 1.0 / n_stores)
            pressure = gap * w
            raw_targets[code] = baseline + pressure

        # Step 3: 约束检查
        constraint_result = self.constraint_checker.check(
            raw_targets, baselines, store_profiles
        )

        # Step 4: 重平衡（因约束调整导致的差额重新分配）
        final_targets = self._rebalance(
            constraint_result.adjusted_targets,
            baselines,
            weights,
            total_target,
            store_profiles,
        )

        # Step 5: 构建分配结果
        allocations = {}
        for code in store_codes:
            baseline = baselines[code]
            target = final_targets.get(code, baseline)
            pressure = target - baseline
            growth = pressure / baseline if baseline > 0 else 0

            is_new = False
            if store_profiles and code in store_profiles:
                profile = store_profiles[code]
                is_new = getattr(profile, "opening_months", 12) < 6

            allocations[code] = AllocationResult(
                store_code=code,
                baseline=baseline,
                weight=weights.get(code, 0),
                pressure=pressure,
                target=target,
                growth_rate=growth,
                is_new_store=is_new,
                constraint_adjusted=target != raw_targets.get(code, baseline),
            )

        plan = AllocationPlan(
            total_target=total_target,
            total_baseline=total_baseline,
            total_gap=gap,
            store_count=n_stores,
            allocations=allocations,
            constraint_result=constraint_result,
        )

        logger.info(
            f"分配完成: {n_stores} 家门店, "
            f"实际分配总额={plan.total_allocated:,.0f} (目标差额={total_target - plan.total_allocated:,.0f}), "
            f"平均增长率={plan.avg_growth_rate:.1%}, "
            f"增长率范围=[{plan.min_growth_rate:.1%}, {plan.max_growth_rate:.1%}]"
        )

        return plan

    def _rebalance(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        weights: dict[str, float],
        total_target: float,
        store_profiles: dict | None,
    ) -> dict[str, float]:
        """重平衡：将约束调整产生的差额重新分配给可调整的门店

        Args:
            targets: 当前目标（可能已被约束调整）
            baselines: 基线值
            weights: 权重
            total_target: 老板总目标

        Returns:
            调整后的目标
        """
        result = dict(targets)
        rounds = 0

        for _ in range(self.max_rebalance_rounds):
            current_total = sum(result.values())
            diff = total_target - current_total

            if abs(diff) < 1:  # 差额 < 1 元，视为平衡
                break

            rounds += 1

            # 找出可调整的门店（未触达约束边界的）
            adjustable = {}
            for code in result:
                baseline = baselines.get(code, 0)
                if baseline <= 0:
                    continue
                floor = baseline * self.constraint_checker.config.floor_ratio
                ceiling = baseline * self.constraint_checker.config.ceiling_ratio
                current = result[code]

                # 如果当前目标在 (floor, ceiling) 之间，说明还可以调整
                if floor < current < ceiling:
                    adjustable[code] = weights.get(code, 0)

            if not adjustable:
                logger.warning(f"重平衡第{rounds}轮: 无门店可调整，停止")
                break

            # 按权重分配差额
            adj_total = sum(adjustable.values())
            if adj_total == 0:
                break

            for code, w in adjustable.items():
                share = diff * w / adj_total
                new_target = result[code] + share

                # 再次检查约束
                baseline = baselines.get(code, 0)
                floor = baseline * self.constraint_checker.config.floor_ratio
                ceiling = baseline * self.constraint_checker.config.ceiling_ratio
                new_target = max(floor, min(ceiling, new_target))

                result[code] = new_target

            logger.debug(
                f"重平衡第{rounds}轮: 差额={diff:,.0f}, "
                f"调整门店={len(adjustable)}, 剩余差额={total_target - sum(result.values()):,.0f}"
            )

        return result

"""公平性检查器

检查承压分配的公平性：
  - 承压率标准差 < 均值的 30%
  - 极端承压门店比例 < 10%
  - 新店承压率低于平均
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger

from src.allocation.target_allocator import AllocationPlan


@dataclass
class FairnessResult:
    """公平性检查结果"""
    avg_pressure_rate: float          # 平均承压率
    std_pressure_rate: float          # 承压率标准差
    cv: float                         # 变异系数 (std / mean)
    max_pressure_rate: float          # 最大承压率
    min_pressure_rate: float          # 最小承压率
    extreme_high_count: int           # 高承压门店数（> 均值 × 1.5）
    extreme_low_count: int            # 低承压门店数（< 均值 × 0.5）
    new_store_avg_pressure: float     # 新店平均承压率
    is_fair: bool                     # 总体是否公平
    issues: list[str]                 # 问题列表

    @property
    def grade(self) -> str:
        """公平性等级"""
        if self.cv < 0.15 and self.is_fair:
            return "A"  # 非常公平
        elif self.cv < 0.30 and self.is_fair:
            return "B"  # 较公平
        elif self.cv < 0.40:
            return "C"  # 一般
        else:
            return "D"  # 不公平


class FairnessChecker:
    """公平性检查器

    使用方式：
        checker = FairnessChecker()
        result = checker.check(allocation_plan)
    """

    def __init__(
        self,
        cv_threshold: float = 0.30,        # 变异系数阈值
        extreme_ratio_threshold: float = 0.10,  # 极端门店比例阈值
        new_store_ratio: float = 0.90,      # 新店承压率应低于平均的 N%
    ):
        self.cv_threshold = cv_threshold
        self.extreme_ratio_threshold = extreme_ratio_threshold
        self.new_store_ratio = new_store_ratio

    def check(self, plan: AllocationPlan) -> FairnessResult:
        """检查分配方案的公平性

        Args:
            plan: 承压分配方案

        Returns:
            FairnessResult
        """
        if not plan.allocations:
            return FairnessResult(
                avg_pressure_rate=0, std_pressure_rate=0, cv=0,
                max_pressure_rate=0, min_pressure_rate=0,
                extreme_high_count=0, extreme_low_count=0,
                new_store_avg_pressure=0, is_fair=True, issues=[],
            )

        # 提取承压率
        pressure_rates = []
        new_store_rates = []
        for alloc in plan.allocations.values():
            rate = alloc.pressure_ratio
            pressure_rates.append(rate)
            if alloc.is_new_store:
                new_store_rates.append(rate)

        avg = np.mean(pressure_rates)
        std = np.std(pressure_rates)
        cv = std / avg if avg != 0 else 0

        # 极端门店
        extreme_high = sum(1 for r in pressure_rates if r > avg * 1.5)
        extreme_low = sum(1 for r in pressure_rates if r < avg * 0.5)

        # 新店承压率
        new_avg = np.mean(new_store_rates) if new_store_rates else 0

        # 检查问题
        issues = []

        if cv > self.cv_threshold:
            issues.append(
                f"承压均匀度不足: 变异系数 {cv:.2%} > 阈值 {self.cv_threshold:.0%}"
            )

        n_stores = len(pressure_rates)
        if extreme_high / n_stores > self.extreme_ratio_threshold:
            issues.append(
                f"高承压门店过多: {extreme_high} 家 ({extreme_high/n_stores:.0%}) "
                f"承压率 > 均值×1.5"
            )

        if extreme_low / n_stores > self.extreme_ratio_threshold:
            issues.append(
                f"低承压门店过多: {extreme_low} 家 ({extreme_low/n_stores:.0%}) "
                f"承压率 < 均值×0.5"
            )

        if new_store_rates and new_avg > avg:
            issues.append(
                f"新店承压过高: 新店平均 {new_avg:.1%} > 整体平均 {avg:.1%}"
            )

        is_fair = len(issues) == 0

        result = FairnessResult(
            avg_pressure_rate=avg,
            std_pressure_rate=std,
            cv=cv,
            max_pressure_rate=max(pressure_rates),
            min_pressure_rate=min(pressure_rates),
            extreme_high_count=extreme_high,
            extreme_low_count=extreme_low,
            new_store_avg_pressure=new_avg,
            is_fair=is_fair,
            issues=issues,
        )

        logger.info(
            f"公平性检查: 等级={result.grade}, "
            f"平均承压率={avg:.1%}, CV={cv:.2%}, "
            f"极端门店={extreme_high + extreme_low}, "
            f"{'通过' if is_fair else '存在问题'}"
        )

        return result

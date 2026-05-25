"""承压分布分析

分析承压分配的分布特征：
  - 承压率分布直方图数据
  - 区域承压差异
  - 门店类型承压差异
  - 异常承压门店识别
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger

from src.allocation.target_allocator import AllocationPlan


@dataclass
class PressureDistributionResult:
    """承压分布分析结果"""
    mean_pressure_rate: float
    median_pressure_rate: float
    std_pressure_rate: float
    p25: float                    # 25 分位
    p75: float                    # 75 分位
    iqr: float                    # 四分位距
    histogram: dict[str, int]     # 分布直方图
    outliers: list[str]           # 异常门店
    by_group: dict[str, dict] | None = None  # 按分组统计


class PressureDistributionAnalyzer:
    """承压分布分析器"""

    def analyze(
        self,
        plan: AllocationPlan,
        store_group_map: dict[str, str] | None = None,
    ) -> PressureDistributionResult:
        """分析承压分布

        Args:
            plan: 分配方案
            store_group_map: {门店编码: 分组名}，用于分组统计

        Returns:
            PressureDistributionResult
        """
        if not plan.allocations:
            return PressureDistributionResult(
                mean_pressure_rate=0, median_pressure_rate=0,
                std_pressure_rate=0, p25=0, p75=0, iqr=0,
                histogram={}, outliers=[],
            )

        # 提取承压率
        rates = {code: a.pressure_ratio for code, a in plan.allocations.items()}
        values = np.array(list(rates.values()))

        # 基本统计
        mean = float(np.mean(values))
        median = float(np.median(values))
        std = float(np.std(values))
        p25 = float(np.percentile(values, 25))
        p75 = float(np.percentile(values, 75))
        iqr = p75 - p25

        # 直方图
        bins = [-0.5, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.5, 1.0]
        labels = ["<-20%", "-20~-10%", "-10~0%", "0~10%", "10~20%", "20~30%", "30~50%", ">50%"]
        hist = {}
        for i in range(len(bins) - 1):
            count = int(np.sum((values >= bins[i]) & (values < bins[i + 1])))
            hist[labels[i]] = count

        # 异常值（超出 IQR 1.5 倍）
        lower = p25 - 1.5 * iqr
        upper = p75 + 1.5 * iqr
        outliers = [code for code, r in rates.items() if r < lower or r > upper]

        # 按分组统计
        by_group = None
        if store_group_map:
            by_group = {}
            for code, rate in rates.items():
                group = store_group_map.get(code, "未知")
                if group not in by_group:
                    by_group[group] = {"rates": [], "count": 0}
                by_group[group]["rates"].append(rate)
                by_group[group]["count"] += 1

            for group in by_group:
                vals = by_group[group]["rates"]
                by_group[group] = {
                    "门店数": len(vals),
                    "平均承压率": float(np.mean(vals)),
                    "最大承压率": float(np.max(vals)),
                    "最小承压率": float(np.min(vals)),
                }

        result = PressureDistributionResult(
            mean_pressure_rate=mean,
            median_pressure_rate=median,
            std_pressure_rate=std,
            p25=p25,
            p75=p75,
            iqr=iqr,
            histogram=hist,
            outliers=outliers,
            by_group=by_group,
        )

        logger.info(
            f"承压分布: 均值={mean:.1%}, 中位数={median:.1%}, "
            f"IQR=[{p25:.1%}, {p75:.1%}], 异常门店={len(outliers)}"
        )

        return result

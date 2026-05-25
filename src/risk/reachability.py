"""目标可达性评估

评估各门店目标的可达性：
  - 目标/基线比值
  - 历史最高 vs 目标
  - 季节性修正后的可达性
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger


@dataclass
class ReachabilityResult:
    """单店可达性评估"""
    store_code: str
    baseline: float
    target: float
    target_ratio: float         # 目标/基线
    historical_max: float       # 历史最高月销
    max_ratio: float            # 目标/历史最高
    risk_level: str             # low / medium / high / critical
    risk_score: float           # 0-100
    suggestion: str


class ReachabilityAssessor:
    """目标可达性评估器

    使用方式：
        assessor = ReachabilityAssessor()
        results = assessor.assess(targets, baselines, historical_monthly)
    """

    def __init__(
        self,
        low_risk_threshold: float = 1.20,     # 低于 120% 为低风险
        medium_risk_threshold: float = 1.50,   # 120%-150% 为中风险
        high_risk_threshold: float = 2.00,     # 150%-200% 为高风险
        # 超过 200% 为极高风险
    ):
        self.thresholds = {
            "low": low_risk_threshold,
            "medium": medium_risk_threshold,
            "high": high_risk_threshold,
        }

    def assess(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        historical_monthly: dict[str, list[float]] | None = None,
    ) -> list[ReachabilityResult]:
        """评估各门店目标可达性

        Args:
            targets: {门店编码: 目标值}
            baselines: {门店编码: 基线值}
            historical_monthly: {门店编码: [月度历史值]}，可选

        Returns:
            各门店的可达性评估结果
        """
        results = []

        for store_code, target in targets.items():
            baseline = baselines.get(store_code, 0)
            ratio = target / baseline if baseline > 0 else 0

            # 历史最高
            monthly = (historical_monthly or {}).get(store_code, [])
            hist_max = max(monthly) if monthly else baseline
            max_ratio = target / hist_max if hist_max > 0 else 0

            # 风险等级
            risk_score, risk_level = self._calc_risk(ratio, max_ratio)

            # 建议
            suggestion = self._get_suggestion(risk_level, ratio)

            results.append(ReachabilityResult(
                store_code=store_code,
                baseline=baseline,
                target=target,
                target_ratio=ratio,
                historical_max=hist_max,
                max_ratio=max_ratio,
                risk_level=risk_level,
                risk_score=risk_score,
                suggestion=suggestion,
            ))

        # 按风险分数排序
        results.sort(key=lambda r: r.risk_score, reverse=True)

        high_count = sum(1 for r in results if r.risk_level in ("high", "critical"))
        logger.info(
            f"可达性评估: {len(results)} 家门店, "
            f"高风险={high_count}, "
            f"最高风险={results[0].store_code}({results[0].risk_level})" if results else ""
        )

        return results

    def _calc_risk(self, ratio: float, max_ratio: float) -> tuple[float, str]:
        """计算风险分数和等级"""
        # 综合考虑目标/基线比和目标/历史最高比
        combined = max(ratio, max_ratio)

        if combined <= self.thresholds["low"]:
            score = combined * 30  # 0-36
            return score, "low"
        elif combined <= self.thresholds["medium"]:
            score = 36 + (combined - self.thresholds["low"]) * 100
            return min(score, 60), "medium"
        elif combined <= self.thresholds["high"]:
            score = 60 + (combined - self.thresholds["medium"]) * 50
            return min(score, 85), "high"
        else:
            score = 85 + (combined - self.thresholds["high"]) * 20
            return min(score, 100), "critical"

    def _get_suggestion(self, risk_level: str, ratio: float) -> str:
        """生成建议"""
        if risk_level == "low":
            return "目标可达，正常执行"
        elif risk_level == "medium":
            return f"目标偏高({ratio:.0%})，需加强促销和客流引导"
        elif risk_level == "high":
            return f"目标高({ratio:.0%})，建议增加营销投入或调整目标"
        else:
            return f"目标极高({ratio:.0%})，强烈建议重新评估目标合理性"

    def to_dataframe(self, results: list[ReachabilityResult]) -> pd.DataFrame:
        """转为 DataFrame"""
        rows = []
        for r in results:
            rows.append({
                "门店编码": r.store_code,
                "基线": round(r.baseline, 0),
                "目标": round(r.target, 0),
                "目标/基线": f"{r.target_ratio:.1%}",
                "历史最高": round(r.historical_max, 0),
                "目标/最高": f"{r.max_ratio:.1%}",
                "风险等级": r.risk_level,
                "风险分数": round(r.risk_score, 1),
                "建议": r.suggestion,
            })
        return pd.DataFrame(rows)

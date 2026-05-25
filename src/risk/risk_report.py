"""风险报告生成器"""

import pandas as pd
from loguru import logger

from src.risk.risk_assessor import RiskAssessment


class RiskReportGenerator:
    """风险报告生成器"""

    def generate_summary_dict(self, assessment: RiskAssessment) -> dict:
        """生成汇总字典"""
        result = {
            "综合风险分": round(assessment.overall_score, 1),
            "综合风险等级": assessment.overall_level,
            "高风险门店数": len(assessment.high_risk_stores),
            "建议数": len(assessment.recommendations),
        }

        for factor in assessment.factors:
            result[f"风险_{factor.name}_分数"] = round(factor.score, 1)
            result[f"风险_{factor.name}_等级"] = factor.level

        if assessment.monte_carlo:
            mc = assessment.monte_carlo
            result["利润均值"] = round(mc.profit_mean, 0)
            result["利润标准差"] = round(mc.profit_std, 0)
            result["亏损概率"] = f"{mc.loss_probability:.1%}"
            result["VaR_95"] = round(mc.var_95, 0)

        return result

    def generate_recommendations(self, assessment: RiskAssessment) -> list[str]:
        """生成建议列表"""
        recs = list(assessment.recommendations)

        if assessment.overall_level == "critical":
            recs.insert(0, "⚠ 综合风险极高，建议暂停方案并重新评估")
        elif assessment.overall_level == "high":
            recs.insert(0, "⚠ 综合风险较高，建议调整后再执行")

        if assessment.monte_carlo and assessment.monte_carlo.loss_probability > 0.2:
            recs.append("建议设置利润预警线，当实际利润低于 VaR95 时触发预警")

        return recs

    def generate_high_risk_stores(
        self, assessment: RiskAssessment
    ) -> pd.DataFrame:
        """生成高风险门店明细"""
        if not assessment.reachability:
            return pd.DataFrame()

        rows = []
        for r in assessment.reachability:
            if r.risk_level in ("high", "critical"):
                rows.append({
                    "门店编码": r.store_code,
                    "基线": round(r.baseline, 0),
                    "目标": round(r.target, 0),
                    "目标/基线": f"{r.target_ratio:.1%}",
                    "风险等级": r.risk_level,
                    "风险分数": round(r.risk_score, 1),
                    "建议": r.suggestion,
                })
        return pd.DataFrame(rows)

"""风险评估 Agent

职责：基于销售数据评估达标风险。
"""

import pandas as pd
from loguru import logger

from src.risk.risk_assessor import RiskAssessor


class RiskAgent:
    """风险评估 Agent"""

    def __init__(self):
        self.name = "RiskAgent"
        self.assessor = RiskAssessor()

    def assess(
        self,
        sales_df: pd.DataFrame,
        targets: dict = None,
    ) -> dict:
        """评估风险

        Args:
            sales_df: 统一销售宽表
            targets: {store_no: target_value}，可选

        Returns:
            {store_risks: {store_no: risk_result}, summary: {...}}
        """
        logger.info(f"[{self.name}] 开始风险评估")

        store_risks = {}
        for store_no in sales_df["store_no"].unique():
            store_data = sales_df[sales_df["store_no"] == store_no]
            target = (targets or {}).get(store_no, store_data["revenue"].mean() * 30)

            result = self.assessor.assess_store_risk(
                store_no=store_no,
                target=target,
                sales_history=store_data,
            )
            store_risks[store_no] = result

        # 汇总
        risk_levels = [r["risk_level"] for r in store_risks.values()]
        summary = {
            "total_stores": len(store_risks),
            "low_risk": risk_levels.count("low"),
            "medium_risk": risk_levels.count("medium"),
            "high_risk": risk_levels.count("high"),
            "critical_risk": risk_levels.count("critical"),
        }

        logger.info(f"[{self.name}] 风险评估完成: {summary}")
        return {"store_risks": store_risks, "summary": summary}

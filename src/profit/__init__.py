"""利润测算模块

计算各门店及公司整体利润，支持成本预估、下钻分析、报告生成。

核心类：
  - ProfitCalculator: 利润计算主逻辑
  - CostEstimator: 成本预估（历史数据/基线推算）
  - DrillDownAnalyzer: 下钻分析（区域/门店类型/渠道）
  - ProfitReportGenerator: 利润报告生成
"""

from src.profit.cost_estimator import CostEstimator, CostStructure
from src.profit.drill_down import DrillDownAnalyzer, DrillDownResult
from src.profit.profit_calculator import ProfitCalculator, ProfitSummary, StoreProfit
from src.profit.profit_report import ProfitReportGenerator

__all__ = [
    "ProfitCalculator", "ProfitSummary", "StoreProfit",
    "CostEstimator", "CostStructure",
    "DrillDownAnalyzer", "DrillDownResult",
    "ProfitReportGenerator",
]

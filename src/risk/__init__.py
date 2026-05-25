"""风险评估模块

综合评估承压分配方案的风险，包括目标可达性、承压均匀度、
利润不确定性（蒙特卡洛）、保底线覆盖率、新店风险等维度。

核心类：
  - RiskAssessor: 风险评估主逻辑
  - ReachabilityAssessor: 目标可达性评估
  - PressureDistributionAnalyzer: 承压分布分析
  - MonteCarloSimulator: 蒙特卡洛情景模拟
  - RiskReportGenerator: 风险报告生成
"""

from src.risk.pressure_distribution import (
    PressureDistributionAnalyzer,
    PressureDistributionResult,
)
from src.risk.reachability import ReachabilityAssessor, ReachabilityResult
from src.risk.risk_assessor import RiskAssessment, RiskAssessor, RiskFactor
from src.risk.risk_report import RiskReportGenerator
from src.risk.scenario_modeler import MonteCarloResult, MonteCarloSimulator

__all__ = [
    "RiskAssessor", "RiskAssessment", "RiskFactor",
    "ReachabilityAssessor", "ReachabilityResult",
    "PressureDistributionAnalyzer", "PressureDistributionResult",
    "MonteCarloSimulator", "MonteCarloResult",
    "RiskReportGenerator",
]

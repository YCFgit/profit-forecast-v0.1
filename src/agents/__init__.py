"""Agent 编排层

协调各专业 Agent 完成利润测算全流程：
  数据采集 → 基线预估 → 承压分配 → 利润测算 → 风险评估

核心类：
  - Orchestrator: 编排器（调度中心）
  - DataAgent: 数据采集 Agent
  - BaselineAgent: 基线预估 Agent
  - AllocationAgent: 承压分配 Agent
  - ProfitAgent: 利润测算 Agent
  - RiskAgent: 风险评估 Agent
"""

from src.agents.data_agent import DataAgent
from src.agents.baseline_agent import BaselineAgent
from src.agents.allocation_agent import AllocationAgent, AllocationResult
from src.agents.profit_agent import ProfitAgent
from src.agents.risk_agent import RiskAgent
from src.agents.orchestrator import Orchestrator

__all__ = [
    "Orchestrator",
    "DataAgent",
    "BaselineAgent",
    "AllocationAgent", "AllocationResult",
    "ProfitAgent",
    "RiskAgent",
]

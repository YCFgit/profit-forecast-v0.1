"""蒙特卡洛情景模拟

通过随机模拟评估利润的不确定性：
  - 收入波动（±10%~20%）
  - 成本波动（±5%~10%）
  - 计算利润的概率分布
  - 输出 VaR（风险价值）和置信区间
"""

from dataclasses import dataclass, field

import numpy as np
from loguru import logger


@dataclass
class MonteCarloResult:
    """蒙特卡洛模拟结果"""
    n_simulations: int
    profit_mean: float
    profit_std: float
    profit_median: float
    profit_p5: float              # 5 分位（VaR 95%）
    profit_p10: float             # 10 分位（VaR 90%）
    profit_p25: float
    profit_p75: float
    profit_p95: float             # 95 分位
    loss_probability: float       # 亏损概率
    profit_distribution: np.ndarray = field(repr=False, default_factory=lambda: np.array([]))

    @property
    def var_95(self) -> float:
        """95% VaR（最大可能亏损）"""
        return -self.profit_p5 if self.profit_p5 < 0 else 0

    @property
    def cvar_95(self) -> float:
        """95% CVaR（条件风险价值）"""
        if len(self.profit_distribution) == 0:
            return 0
        threshold = np.percentile(self.profit_distribution, 5)
        tail = self.profit_distribution[self.profit_distribution <= threshold]
        return float(-np.mean(tail)) if len(tail) > 0 else 0


class MonteCarloSimulator:
    """蒙特卡洛模拟器

    使用方式：
        simulator = MonteCarloSimulator()
        result = simulator.simulate(
            base_revenue=10_000_000,
            base_cost=7_000_000,
            n_simulations=10000,
        )
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def simulate(
        self,
        base_revenue: float,
        base_cost: float,
        revenue_volatility: float = 0.15,   # 收入波动 ±15%
        cost_volatility: float = 0.05,       # 成本波动 ±5%
        n_simulations: int = 10000,
        correlation: float = 0.3,            # 收入-成本相关性
    ) -> MonteCarloResult:
        """运行蒙特卡洛模拟

        Args:
            base_revenue: 基准收入
            base_cost: 基准成本
            revenue_volatility: 收入波动率
            cost_volatility: 成本波动率
            n_simulations: 模拟次数
            correlation: 收入和成本的相关系数

        Returns:
            MonteCarloResult
        """
        # 生成相关随机数
        cov_matrix = np.array([
            [1.0, correlation],
            [correlation, 1.0],
        ])
        # Cholesky 分解
        l = np.linalg.cholesky(cov_matrix)
        z = self.rng.standard_normal((2, n_simulations))
        correlated = l @ z

        # 收入和成本的随机波动
        revenue_shocks = correlated[0] * revenue_volatility
        cost_shocks = correlated[1] * cost_volatility

        revenues = base_revenue * (1 + revenue_shocks)
        costs = base_cost * (1 + cost_shocks)

        # 利润 = 收入 - 成本
        profits = revenues - costs

        # 统计
        result = MonteCarloResult(
            n_simulations=n_simulations,
            profit_mean=float(np.mean(profits)),
            profit_std=float(np.std(profits)),
            profit_median=float(np.median(profits)),
            profit_p5=float(np.percentile(profits, 5)),
            profit_p10=float(np.percentile(profits, 10)),
            profit_p25=float(np.percentile(profits, 25)),
            profit_p75=float(np.percentile(profits, 75)),
            profit_p95=float(np.percentile(profits, 95)),
            loss_probability=float(np.mean(profits < 0)),
            profit_distribution=profits,
        )

        logger.info(
            f"蒙特卡洛模拟({n_simulations}次): "
            f"利润均值={result.profit_mean:,.0f}, "
            f"标准差={result.profit_std:,.0f}, "
            f"亏损概率={result.loss_probability:.1%}, "
            f"VaR95={result.var_95:,.0f}"
        )

        return result

    def simulate_stores(
        self,
        store_revenues: dict[str, float],
        store_costs: dict[str, float],
        n_simulations: int = 5000,
    ) -> dict[str, MonteCarloResult]:
        """逐门店模拟"""
        results = {}
        for code in store_revenues:
            results[code] = self.simulate(
                base_revenue=store_revenues[code],
                base_cost=store_costs.get(code, store_revenues[code] * 0.7),
                n_simulations=n_simulations,
            )
        return results

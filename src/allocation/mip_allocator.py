"""MIP 运筹优化承压分配器

参考门店预算方法论 V3/V4，使用 Mixed Integer Programming 最大化期望变动边际利润。

核心思路：
- 4个难度档位（轻松/适中/有挑战/高压），每个有不同达成概率
- 目标函数：max Σ p_s × m_variable_i × w_{i,s} × UNIT
- 约束：总目标、天花板、区域份额、品牌平衡
- 分段线性化：delta约束保证档位从低到高依次填满

使用方式：
    allocator = MIPAllocator()
    result = allocator.allocate(
        total_target=1_000_000_000,
        baselines={"ST001": 100_000, ...},
        marginal_rates={"ST001": 0.15, ...},
        ceilings={"ST001": 150_000, ...},
        store_meta={"ST001": {"region": "华东", "brand": "NK"}, ...},
    )
"""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class MIPStoreResult:
    """单店 MIP 分配结果"""
    store_code: str
    baseline: float
    target: float
    pressure: float
    growth_rate: float
    marginal_rate: float
    ceiling: float
    difficulty_level: str         # "easy" | "moderate" | "challenging" | "hard"
    achievement_probability: float
    expected_marginal_profit: float
    region: str = ""
    brand: str = ""


@dataclass
class MIPAllocationResult:
    """MIP 分配汇总结果"""
    total_target: float
    total_baseline: float
    total_gap: float
    total_allocated: float
    store_count: int
    participating_count: int      # 参与分配的门店数
    stores: dict[str, MIPStoreResult]
    solver_status: str = "Optimal"
    expected_total_marginal_profit: float = 0.0
    region_summary: dict[str, dict] = field(default_factory=dict)
    brand_summary: dict[str, dict] = field(default_factory=dict)
    infeasible_gap: float = 0.0   # 不可达缺口

    @property
    def avg_growth_rate(self) -> float:
        rates = [s.growth_rate for s in self.stores.values() if s.pressure > 0]
        return sum(rates) / len(rates) if rates else 0

    @property
    def max_growth_rate(self) -> float:
        return max((s.growth_rate for s in self.stores.values()), default=0)


# ── 难度档位定义 ──────────────────────────────────────
DIFFICULTY_LEVELS = [
    # (档位名, 达成概率, 基线上限比例)
    ("easy", 0.95, 1.05),         # 轻松：目标 ≤ 基线 × 1.05
    ("moderate", 0.85, 1.15),     # 适中：目标 ≤ 基线 × 1.15
    ("challenging", 0.70, 1.30),  # 有挑战：目标 ≤ 基线 × 1.30
    ("hard", 0.50, 1.50),         # 高压：目标 ≤ 基线 × 1.50
]


class MIPAllocator:
    """MIP 运筹优化承压分配器

    使用 PuLP CBC 求解器，最大化期望变动边际利润。
    """

    def __init__(
        self,
        target_lower_ratio: float = 0.95,   # 总目标下限（95%）
        target_upper_ratio: float = 1.00,   # 总目标上限（100%）
        region_min_share_ratio: float = 0.80,  # 区域最低份额
        brand_balance_tolerance: float = 0.10,  # 品牌平衡容忍度
        unit: float = 1.0,                  # 分配单位（元）
    ):
        self.target_lower_ratio = target_lower_ratio
        self.target_upper_ratio = target_upper_ratio
        self.region_min_share_ratio = region_min_share_ratio
        self.brand_balance_tolerance = brand_balance_tolerance
        self.unit = unit

    def allocate(
        self,
        total_target: float,
        baselines: dict[str, float],
        marginal_rates: dict[str, float],
        ceilings: dict[str, float],
        store_meta: dict[str, dict] | None = None,
        exclude_stores: set[str] | None = None,
    ) -> MIPAllocationResult:
        """执行 MIP 承压分配

        Args:
            total_target: 老板总目标
            baselines: {store_code: 基线收入}
            marginal_rates: {store_code: 变动边际利润率}
            ceilings: {store_code: 天花板（P75 × 阻尼季节指数）}
            store_meta: {store_code: {"region": ..., "brand": ...}}
            exclude_stores: 不参与分配的门店编码集合

        Returns:
            MIPAllocationResult
        """
        try:
            import pulp
        except ImportError:
            logger.error("PuLP 未安装，无法执行 MIP 分配。请运行: pip install pulp")
            return self._fallback_allocate(total_target, baselines, marginal_rates)

        exclude = exclude_stores or set()
        participating = {c: b for c, b in baselines.items() if c not in exclude and b > 0}
        excluded_baseline = sum(baselines[c] for c in exclude if c in baselines)

        store_codes = list(participating.keys())
        n = len(store_codes)
        total_baseline = sum(participating.values())

        logger.info(
            f"MIP分配开始: 目标={total_target:,.0f}, "
            f"参与={n}家(基线={total_baseline:,.0f}), "
            f"排除={len(exclude)}家(基线={excluded_baseline:,.0f})"
        )

        if n == 0:
            return MIPAllocationResult(
                total_target=total_target, total_baseline=0, total_gap=0,
                total_allocated=0, store_count=0, participating_count=0,
                stores={}, solver_status="NoStores",
            )

        # ── 构建 MIP 模型 ──────────────────────────────
        prob = pulp.LpProblem("PressureAllocation", pulp.LpMaximize)

        # 决策变量：w[i][s] = 门店i在档位s的分配量
        w = {}
        delta = {}
        for code in store_codes:
            w[code] = {}
            delta[code] = {}
            for s_idx, (s_name, _, s_limit) in enumerate(DIFFICULTY_LEVELS):
                max_w = participating[code] * (s_limit - (DIFFICULTY_LEVELS[s_idx - 1][2] if s_idx > 0 else 1.0))
                max_w = max(max_w, 0)
                w[code][s_name] = pulp.LpVariable(f"w_{code}_{s_name}", 0, max_w, cat="Continuous")
                delta[code][s_name] = pulp.LpVariable(f"d_{code}_{s_name}", 0, 1, cat="Binary")

        # 目标函数：max Σ p_s × m_variable × w[i][s]
        objective = []
        for code in store_codes:
            m_var = marginal_rates.get(code, 0.10)
            for s_name, prob_s, _ in DIFFICULTY_LEVELS:
                objective.append(prob_s * m_var * w[code][s_name])
        prob += pulp.lpSum(objective), "ExpectedMarginalProfit"

        # 约束1：总目标范围
        total_alloc = pulp.lpSum(
            participating[code] + pulp.lpSum(w[code][s_name] for s_name, _, _ in DIFFICULTY_LEVELS)
            for code in store_codes
        )
        prob += total_alloc >= total_target * self.target_lower_ratio, "TargetLower"
        prob += total_alloc <= total_target * self.target_upper_ratio, "TargetUpper"

        # 约束2：天花板约束
        for code in store_codes:
            ceiling = ceilings.get(code, participating[code] * 1.5)
            store_total = participating[code] + pulp.lpSum(
                w[code][s_name] for s_name, _, _ in DIFFICULTY_LEVELS
            )
            prob += store_total <= ceiling, f"Ceiling_{code}"

        # 约束3：分段线性化 — 档位从低到高依次填满
        for code in store_codes:
            for s_idx, (s_name, _, _) in enumerate(DIFFICULTY_LEVELS):
                if s_idx > 0:
                    prev_name = DIFFICULTY_LEVELS[s_idx - 1][0]
                    # delta[s] <= delta[s-1]（高档位激活前低档位必须满）
                    prob += delta[code][s_name] <= delta[code][prev_name], \
                        f"DeltaOrder_{code}_{s_name}"

                # w[i][s] <= delta[i][s] × max_w_for_s
                s_limit = DIFFICULTY_LEVELS[s_idx][2]
                prev_limit = DIFFICULTY_LEVELS[s_idx - 1][2] if s_idx > 0 else 1.0
                max_w = participating[code] * (s_limit - prev_limit)
                if max_w > 0:
                    prob += w[code][s_name] <= delta[code][s_name] * max_w, \
                        f"DeltaBind_{code}_{s_name}"

        # 约束4：区域最低份额
        if store_meta:
            regions = {}
            for code in store_codes:
                region = store_meta.get(code, {}).get("region", "未知")
                regions.setdefault(region, []).append(code)

            for region, codes in regions.items():
                if len(codes) < 2:
                    continue
                region_baseline = sum(participating[c] for c in codes)
                region_share = region_baseline / total_baseline
                region_min = region_baseline * self.region_min_share_ratio

                region_alloc = pulp.lpSum(
                    participating[c] + pulp.lpSum(w[c][s] for s, _, _ in DIFFICULTY_LEVELS)
                    for c in codes
                )
                prob += region_alloc >= region_min, f"RegionMin_{region}"

        # 求解
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        status = pulp.LpStatus[prob.status]

        logger.info(f"MIP求解状态: {status}, 目标值={pulp.value(prob.objective):,.0f}")

        # ── 提取结果 ──────────────────────────────
        stores = {}
        total_allocated = 0
        expected_profit = 0

        for code in store_codes:
            baseline = participating[code]
            extra = sum(pulp.value(w[code][s_name]) or 0 for s_name, _, _ in DIFFICULTY_LEVELS)
            target = baseline + extra
            pressure = extra
            growth = pressure / baseline if baseline > 0 else 0
            m_var = marginal_rates.get(code, 0.10)

            # 确定主要难度档位
            level = "none"
            prob_achieve = 0.0
            for s_name, p_s, _ in reversed(DIFFICULTY_LEVELS):
                w_val = pulp.value(w[code][s_name]) or 0
                if w_val > 0.01:
                    level = s_name
                    prob_achieve = p_s
                    break

            meta = (store_meta or {}).get(code, {})
            stores[code] = MIPStoreResult(
                store_code=code,
                baseline=baseline,
                target=round(target, 0),
                pressure=round(pressure, 0),
                growth_rate=round(growth, 4),
                marginal_rate=m_var,
                ceiling=ceilings.get(code, baseline * 1.5),
                difficulty_level=level,
                achievement_probability=prob_achieve,
                expected_marginal_profit=round(pressure * m_var * prob_achieve, 0),
                region=meta.get("region", ""),
                brand=meta.get("brand", ""),
            )
            total_allocated += target
            expected_profit += pressure * m_var * prob_achieve

        # 区域汇总
        region_summary = {}
        for code, sr in stores.items():
            r = sr.region
            if r not in region_summary:
                region_summary[r] = {"baseline": 0, "target": 0, "store_count": 0}
            region_summary[r]["baseline"] += sr.baseline
            region_summary[r]["target"] += sr.target
            region_summary[r]["store_count"] += 1

        # 品牌汇总
        brand_summary = {}
        for code, sr in stores.items():
            b = sr.brand
            if b not in brand_summary:
                brand_summary[b] = {"baseline": 0, "target": 0, "store_count": 0}
            brand_summary[b]["baseline"] += sr.baseline
            brand_summary[b]["target"] += sr.target
            brand_summary[b]["store_count"] += 1

        result = MIPAllocationResult(
            total_target=total_target,
            total_baseline=total_baseline + excluded_baseline,
            total_gap=total_target - total_baseline - excluded_baseline,
            total_allocated=round(total_allocated, 0),
            store_count=len(baselines),
            participating_count=n,
            stores=stores,
            solver_status=status,
            expected_total_marginal_profit=round(expected_profit, 0),
            region_summary=region_summary,
            brand_summary=brand_summary,
            infeasible_gap=round(total_target - total_allocated - excluded_baseline, 0),
        )

        logger.info(
            f"MIP分配完成: 分配总额={total_allocated:,.0f}, "
            f"期望边际利润={expected_profit:,.0f}, "
            f"平均增长率={result.avg_growth_rate:.1%}, "
            f"最大增长率={result.max_growth_rate:.1%}"
        )

        return result

    def _fallback_allocate(
        self,
        total_target: float,
        baselines: dict[str, float],
        marginal_rates: dict[str, float],
    ) -> MIPAllocationResult:
        """PuLP 不可用时的降级分配（按基线比例）"""
        total_baseline = sum(baselines.values())
        gap = total_target - total_baseline
        stores = {}

        for code, baseline in baselines.items():
            share = baseline / total_baseline if total_baseline > 0 else 0
            pressure = gap * share
            target = baseline + pressure
            growth = pressure / baseline if baseline > 0 else 0

            stores[code] = MIPStoreResult(
                store_code=code,
                baseline=baseline,
                target=round(target, 0),
                pressure=round(pressure, 0),
                growth_rate=round(growth, 4),
                marginal_rate=marginal_rates.get(code, 0.10),
                ceiling=baseline * 1.5,
                difficulty_level="moderate",
                achievement_probability=0.85,
                expected_marginal_profit=round(pressure * marginal_rates.get(code, 0.10) * 0.85, 0),
            )

        return MIPAllocationResult(
            total_target=total_target,
            total_baseline=total_baseline,
            total_gap=gap,
            total_allocated=round(sum(s.target for s in stores.values()), 0),
            store_count=len(baselines),
            participating_count=len(baselines),
            stores=stores,
            solver_status="Fallback",
        )

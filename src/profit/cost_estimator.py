"""成本预估器

根据历史成本结构和目标收入，预估各门店的成本。
支持：
  - 按历史成本率推算
  - 按固定+变动成本模型推算
  - 考虑规模效应（收入越高，固定成本占比越低）
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger


@dataclass
class CostStructure:
    """成本结构"""
    store_code: str
    cogs_ratio: float           # 采购成本率
    salary: float               # 人工成本（固定）
    rent: float                 # 租金（固定）
    property_fee: float         # 物业费（固定）
    marketing: float            # 营销费用（半变动）
    logistics: float            # 物流费用（变动）
    depreciation: float         # 折旧（固定）
    other_expense: float        # 其他费用

    @property
    def fixed_cost(self) -> float:
        """固定成本"""
        return self.salary + self.rent + self.property_fee + self.depreciation

    @property
    def variable_cost_ratio(self) -> float:
        """变动成本率（不含 COGS）"""
        return 0.07  # 营销+物流+其他


class CostEstimator:
    """成本预估器

    使用方式：
        estimator = CostEstimator()
        cost_structures = estimator.estimate_from_history(
            targets={"ST0001": 500_000},
            historical_costs={"ST0001": {...}},
        )
    """

    def __init__(
        self,
        default_cogs_ratio: float = 0.45,
        default_salary_ratio: float = 0.10,
        default_rent_ratio: float = 0.05,
        scale_effect_factor: float = 0.02,  # 规模效应：收入每增 10%，固定成本率降 2%
    ):
        self.default_cogs_ratio = default_cogs_ratio
        self.default_salary_ratio = default_salary_ratio
        self.default_rent_ratio = default_rent_ratio
        self.scale_effect_factor = scale_effect_factor

    def estimate_from_history(
        self,
        targets: dict[str, float],
        historical_costs: dict[str, dict[str, float]],
        historical_revenues: dict[str, float] | None = None,
    ) -> dict[str, dict[str, float]]:
        """根据历史成本结构预估

        Args:
            targets: {门店编码: 目标收入}
            historical_costs: {门店编码: 历史成本明细}
            historical_revenues: {门店编码: 历史收入}，用于计算规模效应

        Returns:
            {门店编码: 预估成本明细}
        """
        result = {}

        for store_code, target in targets.items():
            hist = historical_costs.get(store_code, {})
            hist_rev = (historical_revenues or {}).get(store_code, target)

            # 采购成本率（直接沿用历史值或默认值）
            cogs_ratio = hist.get("cogs_ratio", self.default_cogs_ratio)

            # 固定成本（考虑规模效应）
            scale_factor = self._calc_scale_factor(target, hist_rev)

            salary = hist.get("salary", target * self.default_salary_ratio)
            rent = hist.get("rent", target * self.default_rent_ratio)
            property_fee = hist.get("property_fee", target * 0.02)
            depreciation = hist.get("depreciation", target * 0.01)

            # 固定成本按规模效应调整
            salary *= scale_factor
            rent *= scale_factor
            property_fee *= scale_factor
            depreciation *= scale_factor

            # 变动成本（按收入比例）
            marketing = hist.get("marketing", target * 0.03)
            logistics = hist.get("logistics", target * 0.02)
            other_expense = hist.get("other_expense", target * 0.02)

            result[store_code] = {
                "cogs_ratio": cogs_ratio,
                "salary": salary,
                "rent": rent,
                "property_fee": property_fee,
                "marketing": marketing,
                "logistics": logistics,
                "depreciation": depreciation,
                "other_expense": other_expense,
            }

        logger.info(f"成本预估完成: {len(result)} 家门店")
        return result

    def estimate_from_baselines(
        self,
        targets: dict[str, float],
        baselines: dict[str, float],
        baseline_cost_structures: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, dict[str, float]]:
        """根据基线成本结构预估目标成本

        Args:
            targets: {门店编码: 目标收入}
            baselines: {门店编码: 基线收入}
            baseline_cost_structures: {门店编码: 基线成本明细}

        Returns:
            {门店编码: 预估成本明细}
        """
        result = {}

        for store_code, target in targets.items():
            baseline = baselines.get(store_code, target)
            base_costs = (baseline_cost_structures or {}).get(store_code, {})

            # 成本率沿用基线
            cogs_ratio = base_costs.get("cogs_ratio", self.default_cogs_ratio)

            # 固定成本不变（不随收入增长）
            salary = base_costs.get("salary", baseline * self.default_salary_ratio)
            rent = base_costs.get("rent", baseline * self.default_rent_ratio)
            property_fee = base_costs.get("property_fee", baseline * 0.02)
            depreciation = base_costs.get("depreciation", baseline * 0.01)

            # 变动成本按目标收入重新计算
            marketing = target * base_costs.get("marketing_ratio", 0.03)
            logistics = target * base_costs.get("logistics_ratio", 0.02)
            other_expense = target * base_costs.get("other_ratio", 0.02)

            result[store_code] = {
                "cogs_ratio": cogs_ratio,
                "salary": salary,
                "rent": rent,
                "property_fee": property_fee,
                "marketing": marketing,
                "logistics": logistics,
                "depreciation": depreciation,
                "other_expense": other_expense,
            }

        logger.info(f"成本预估完成（基于基线）: {len(result)} 家门店")
        return result

    def from_store_loss_data(
        self,
        store_loss_df: pd.DataFrame,
        targets: dict[str, float],
        months: int = 3,
        revenue_perspective: str = "actual",
    ) -> dict[str, dict[str, float]]:
        """从真实门店损益数据构建成本结构

        Args:
            store_loss_df: fetch_store_loss() 返回的 DataFrame
            targets: {门店编码: 目标收入}
            months: 取最近 N 个月的平均值
            revenue_perspective: "actual" = 业绩口径, "rebate" = 返利口径

        Returns:
            {门店编码: 成本明细dict}，与 estimate_from_baselines 格式兼容
        """
        if store_loss_df.empty:
            logger.warning("门店损益数据为空，回退到默认成本结构")
            return self.estimate_from_baselines(targets, targets)

        sales_col = "rebate_sales" if revenue_perspective == "rebate" else "actual_sales_pp"

        df = store_loss_df.copy()
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["year_month"] = df["sale_date"].dt.to_period("M")

        # 取最近 N 个月
        all_months = sorted(df["year_month"].unique(), reverse=True)
        recent_months = all_months[:months]
        df = df[df["year_month"].isin(recent_months)]

        result = {}

        for store_code in df["store_code"].unique():
            store_df = df[df["store_code"] == store_code]
            if store_df.empty:
                continue

            # 按月汇总后取均值
            monthly = store_df.groupby("year_month").agg({
                sales_col: "sum",
                "actual_cost": "sum",
                "actual_gross_profit": "sum",
                "actual_salary": "sum",
                "actual_social_fee": "sum",
                "actual_operating_expense": "sum",
                "actual_b_manage_expense": "sum",
                "actual_mall_fee": "sum",
                "actual_express": "sum",
                "actual_other_fee": "sum",
                "actual_decorate_fee": "sum",
            }).mean()

            rev = monthly[sales_col]
            if rev <= 0:
                continue

            cogs_ratio = monthly["actual_cost"] / rev
            total_salary = monthly["actual_salary"] + monthly["actual_social_fee"]

            # 租金 = 经营费用 - 已知明细项（残差估算）
            remaining_opex = (
                monthly["actual_operating_expense"]
                - monthly["actual_salary"]
                - monthly["actual_social_fee"]
                - monthly["actual_mall_fee"]
                - monthly["actual_express"]
                - monthly["actual_other_fee"]
                - monthly["actual_decorate_fee"]
            )
            rent_and_property = max(0, remaining_opex)

            b_manage = monthly["actual_b_manage_expense"]

            result[store_code] = {
                "cogs_ratio": round(min(0.80, max(0.20, cogs_ratio)), 4),
                "salary": round(total_salary, 2),
                "rent": round(rent_and_property, 2),
                "property_fee": 0.0,
                "marketing": round(monthly["actual_mall_fee"], 2),
                "logistics": round(monthly["actual_express"] + b_manage * 0.3, 2),
                "depreciation": round(monthly["actual_decorate_fee"], 2),
                "other_expense": round(monthly["actual_other_fee"] + b_manage * 0.7, 2),
                "data_source": "real",
            }

        # 无数据门店降级到默认值
        for store_code in targets:
            if store_code not in result:
                result[store_code] = {
                    "cogs_ratio": self.default_cogs_ratio,
                    "salary": targets[store_code] * self.default_salary_ratio,
                    "rent": targets[store_code] * self.default_rent_ratio,
                    "property_fee": targets[store_code] * 0.02,
                    "marketing": targets[store_code] * 0.03,
                    "logistics": targets[store_code] * 0.02,
                    "depreciation": targets[store_code] * 0.01,
                    "other_expense": targets[store_code] * 0.02,
                }

        real_count = sum(1 for v in result.values() if v.get("data_source") == "real")
        logger.info(
            f"从损益数据构建成本结构: {len(result)} 家门店, "
            f"{real_count} 家使用真实数据, {len(result) - real_count} 家使用默认值"
        )
        return result

    def _calc_scale_factor(self, target: float, baseline: float) -> float:
        """计算规模效应系数

        收入越高，固定成本率越低（但不会低于 0.8）
        """
        if baseline <= 0:
            return 1.0
        ratio = target / baseline
        # 每增长 10%，固定成本率降低 scale_effect_factor
        factor = 1.0 - (ratio - 1.0) * self.scale_effect_factor * 10
        return max(0.8, min(1.2, factor))

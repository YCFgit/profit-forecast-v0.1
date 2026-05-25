"""利润测算主逻辑

根据分配目标和成本结构，计算各门店和整体的利润。

计算公式：
  单店收入 = 分配目标 T_i（或基线收入）
  单店成本 = 采购成本 + 人工成本 + 租金 + 物流 + 营销 + 其他
  单店毛利 = 收入 - 采购成本
  单店净利 = 毛利 - 运营费用 - 税费
  公司利润 = Σ 各店利润
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from loguru import logger


@dataclass
class StoreProfit:
    """单店利润测算结果"""
    store_code: str
    revenue: float                    # 收入（目标或基线）
    cost_of_goods: float              # 采购成本（COGS）
    gross_profit: float               # 毛利
    gross_margin: float               # 毛利率
    operating_expense: float          # 运营费用
    salary: float                     # 人工成本
    rent: float                       # 租金
    property_fee: float               # 物业费
    marketing: float                  # 营销费用
    logistics: float                  # 物流费用
    depreciation: float               # 折旧
    other_expense: float              # 其他费用
    total_expense: float              # 总费用
    operating_profit: float           # 营业利润
    operating_margin: float           # 营业利润率
    tax: float                        # 税费
    net_profit: float                 # 净利润
    net_margin: float                 # 净利率
    # 真实损益数据扩展字段
    social_fee: float = 0.0           # 社保公积金
    mall_fee: float = 0.0             # 商场综合收费
    warehousing: float = 0.0          # 仓储物流费
    b_manage_expense: float = 0.0     # B管理费用
    data_source: str = "default"      # "real" | "default"
    revenue_perspective: str = "actual"  # "actual" | "rebate"


@dataclass
class ProfitSummary:
    """利润测算汇总"""
    total_revenue: float
    total_cogs: float
    total_gross_profit: float
    avg_gross_margin: float
    total_operating_expense: float
    total_operating_profit: float
    avg_operating_margin: float
    total_tax: float
    total_net_profit: float
    avg_net_margin: float
    store_count: int
    profitable_count: int             # 盈利门店数
    loss_count: int                   # 亏损门店数
    store_profits: dict[str, StoreProfit] = field(default_factory=dict)

    @property
    def profit_rate(self) -> float:
        """盈利门店占比"""
        return self.profitable_count / self.store_count if self.store_count > 0 else 0


class ProfitCalculator:
    """利润测算器

    使用方式：
        calc = ProfitCalculator()
        summary = calc.calculate(
            targets={"ST0001": 500_000, ...},
            cost_structures={"ST0001": {...}, ...},
        )
    """

    def __init__(
        self,
        tax_rate: float = 0.25,           # 所得税率
        avg_cogs_ratio: float = 0.45,      # 默认采购成本率
        avg_operating_ratio: float = 0.20, # 默认运营费用率
    ):
        self.tax_rate = tax_rate
        self.avg_cogs_ratio = avg_cogs_ratio
        self.avg_operating_ratio = avg_operating_ratio

    def calculate(
        self,
        targets: dict[str, float],
        cost_structures: dict[str, dict[str, float]] | None = None,
    ) -> ProfitSummary:
        """测算利润

        Args:
            targets: {门店编码: 目标收入}
            cost_structures: {门店编码: 成本明细}
                可选字段: cogs_ratio, salary, rent, property_fee,
                marketing, logistics, depreciation, other_expense

        Returns:
            ProfitSummary
        """
        store_profits = {}

        for store_code, revenue in targets.items():
            costs = (cost_structures or {}).get(store_code, {})

            # 采购成本
            cogs_ratio = costs.get("cogs_ratio", self.avg_cogs_ratio)
            cogs = revenue * cogs_ratio

            # 毛利
            gross_profit = revenue - cogs
            gross_margin = gross_profit / revenue if revenue > 0 else 0

            # 运营费用明细
            salary = costs.get("salary", revenue * 0.10)
            rent = costs.get("rent", revenue * 0.05)
            property_fee = costs.get("property_fee", revenue * 0.02)
            marketing = costs.get("marketing", revenue * 0.03)
            logistics = costs.get("logistics", revenue * 0.02)
            depreciation = costs.get("depreciation", revenue * 0.01)
            other_expense = costs.get("other_expense", revenue * 0.02)

            operating_expense = (
                salary + rent + property_fee + marketing +
                logistics + depreciation + other_expense
            )

            # 营业利润
            operating_profit = gross_profit - operating_expense
            operating_margin = operating_profit / revenue if revenue > 0 else 0

            # 税费（盈利才交税）
            tax = max(0, operating_profit * self.tax_rate)

            # 净利润
            net_profit = operating_profit - tax
            net_margin = net_profit / revenue if revenue > 0 else 0

            store_profits[store_code] = StoreProfit(
                store_code=store_code,
                revenue=revenue,
                cost_of_goods=cogs,
                gross_profit=gross_profit,
                gross_margin=gross_margin,
                operating_expense=operating_expense,
                salary=salary,
                rent=rent,
                property_fee=property_fee,
                marketing=marketing,
                logistics=logistics,
                depreciation=depreciation,
                other_expense=other_expense,
                total_expense=cogs + operating_expense,
                operating_profit=operating_profit,
                operating_margin=operating_margin,
                tax=tax,
                net_profit=net_profit,
                net_margin=net_margin,
                social_fee=costs.get("social_fee", 0.0),
                mall_fee=costs.get("mall_fee", 0.0),
                warehousing=costs.get("warehousing", 0.0),
                b_manage_expense=costs.get("b_manage_expense", 0.0),
                data_source="real" if costs.get("data_source") == "real" else "default",
                revenue_perspective=costs.get("revenue_perspective", "actual"),
            )

        # 汇总
        profitable = sum(1 for p in store_profits.values() if p.net_profit > 0)
        loss = sum(1 for p in store_profits.values() if p.net_profit < 0)
        total_revenue = sum(p.revenue for p in store_profits.values())

        summary = ProfitSummary(
            total_revenue=total_revenue,
            total_cogs=sum(p.cost_of_goods for p in store_profits.values()),
            total_gross_profit=sum(p.gross_profit for p in store_profits.values()),
            avg_gross_margin=sum(p.gross_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
            total_operating_expense=sum(p.operating_expense for p in store_profits.values()),
            total_operating_profit=sum(p.operating_profit for p in store_profits.values()),
            avg_operating_margin=sum(p.operating_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
            total_tax=sum(p.tax for p in store_profits.values()),
            total_net_profit=sum(p.net_profit for p in store_profits.values()),
            avg_net_margin=sum(p.net_profit for p in store_profits.values()) / total_revenue if total_revenue > 0 else 0,
            store_count=len(store_profits),
            profitable_count=profitable,
            loss_count=loss,
            store_profits=store_profits,
        )

        logger.info(
            f"利润测算完成: {summary.store_count} 家门店, "
            f"总收入={summary.total_revenue:,.0f}, "
            f"净利润={summary.total_net_profit:,.0f}({summary.avg_net_margin:.1%}), "
            f"盈利={profitable}, 亏损={loss}"
        )

        return summary

    def to_dataframe(self, summary: ProfitSummary) -> pd.DataFrame:
        """将利润明细转为 DataFrame"""
        rows = []
        for code, sp in sorted(summary.store_profits.items()):
            rows.append({
                "门店编码": code,
                "收入": round(sp.revenue, 0),
                "采购成本": round(sp.cost_of_goods, 0),
                "毛利": round(sp.gross_profit, 0),
                "毛利率": f"{sp.gross_margin:.1%}",
                "人工": round(sp.salary, 0),
                "租金": round(sp.rent, 0),
                "营销": round(sp.marketing, 0),
                "物流": round(sp.logistics, 0),
                "运营费用": round(sp.operating_expense, 0),
                "营业利润": round(sp.operating_profit, 0),
                "营业利润率": f"{sp.operating_margin:.1%}",
                "税费": round(sp.tax, 0),
                "净利润": round(sp.net_profit, 0),
                "净利率": f"{sp.net_margin:.1%}",
                "数据来源": sp.data_source,
            })
        return pd.DataFrame(rows)

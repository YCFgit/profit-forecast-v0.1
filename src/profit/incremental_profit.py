"""增量利润推算器

参考预算方法论 V3/V4，实现变动/固定成本分离和增量利润计算。

核心思想：
- 加压时只有变动成本增加（含税成本、商场扣点、附加税随收入增长）
- 固定成本不随加压变动（租金、人工、物业、管理费以基线为锚）

变动边际利润率公式（MIP目标函数核心）：
    m_variable = 1 - cost_rate/disc_rate - mall_fee_rate + rebate_rate/disc_rate

利润推算完整公式链：
    牌价收入 = 期望收入 / 折扣率
    毛利 = 期望收入 × 毛利率
    商场扣点 = 期望收入 × 商场扣点率
    附加税 = 期望收入 × 附加税率
    变动边际利润 = 毛利 - 商场扣点 - 附加税
    固定费用 = 基线 × (费用率 - 商场扣点率)
    管理费用 = 基线 × 管理费用率
    经营利润 = 变动边际利润 - 固定费用 - 管理费用
    净利润 = 经营利润 + 平台返利
"""

from dataclasses import dataclass, field

from loguru import logger


# ── 全国兜底默认比率 ──────────────────────────────
NATIONAL_DEFAULTS = {
    "discount_rate": 0.75,
    "cost_rate": 0.49,
    "mall_fee_rate": 0.15,
    "expense_rate": 0.30,
    "managing_exp_rate": 0.024,
    "nonoperating_rate": 0.005,
    "rebate_rate": 0.011,
    "return_commission_rate": 0.005,
}


@dataclass
class StoreCostRates:
    """门店成本比率结构"""
    store_code: str
    discount_rate: float = 0.75       # 折扣率 = 收入/牌价
    cost_rate: float = 0.49           # 成本率（基于牌价）
    mall_fee_rate: float = 0.15       # 商场扣点率（基于收入）
    expense_rate: float = 0.30        # 经营费用率（基于收入）
    managing_exp_rate: float = 0.024  # 管理费用率（基于收入）
    nonoperating_rate: float = 0.005  # 营业外收支率（基于收入）
    rebate_rate: float = 0.011        # 返利率（基于牌价）
    return_commission_rate: float = 0.005  # 退货佣金率（基于收入）

    @property
    def m_variable(self) -> float:
        """变动边际利润率（MIP目标函数核心）

        m_variable = 1 - cost_rate/disc_rate - mall_fee_rate + rebate_rate/disc_rate
        """
        disc = max(self.discount_rate, 0.30)
        return (
            1.0
            - self.cost_rate / disc
            - self.mall_fee_rate
            + self.rebate_rate / disc
        )

    @property
    def m_full(self) -> float:
        """全口径边际利润率（含固定费用，用于对比分析）"""
        disc = max(self.discount_rate, 0.30)
        return (
            1.0
            - self.cost_rate / disc
            - self.expense_rate
            - self.managing_exp_rate
            - self.nonoperating_rate
            + self.rebate_rate / disc
        )


@dataclass
class StoreProfitDetail:
    """单店增量利润明细"""
    store_code: str
    baseline: float
    expected_revenue: float
    extra_target: float
    achievement_prob: float

    # 收入分解
    list_price: float = 0.0          # 牌价收入
    gross_profit: float = 0.0        # 毛利
    gross_margin: float = 0.0        # 毛利率

    # 变动成本（随收入变动）
    mall_fee: float = 0.0            # 商场扣点
    additional_tax: float = 0.0      # 附加税
    variable_margin: float = 0.0     # 变动边际利润

    # 固定成本（以基线为锚）
    fixed_expense: float = 0.0       # 固定经营费用
    managing_expense: float = 0.0    # 管理费用
    nonoperating: float = 0.0        # 营业外收支

    # 利润
    operating_profit: float = 0.0    # 经营利润
    platform_rebate: float = 0.0     # 平台返利
    return_commission: float = 0.0   # 退货佣金
    net_profit: float = 0.0          # 净利润

    # 比率
    m_variable: float = 0.0          # 变动边际利润率
    m_full: float = 0.0              # 全口径边际利润率


@dataclass
class IncrementalProfitResult:
    """增量利润推算汇总"""
    total_baseline: float
    total_expected_revenue: float
    total_variable_margin: float
    total_net_profit: float
    avg_m_variable: float
    store_count: int
    stores: dict[str, StoreProfitDetail] = field(default_factory=dict)
    region_summary: dict[str, dict] = field(default_factory=dict)
    brand_summary: dict[str, dict] = field(default_factory=dict)


class IncrementalProfitCalculator:
    """增量利润推算器

    使用方式：
        calc = IncrementalProfitCalculator()
        result = calc.calculate(
            baselines={"ST001": 100000, ...},
            targets={"ST001": 120000, ...},
            cost_rates={"ST001": StoreCostRates(...), ...},
            achievement_probs={"ST001": 0.85, ...},
        )
    """

    def calculate(
        self,
        baselines: dict[str, float],
        targets: dict[str, float],
        cost_rates: dict[str, StoreCostRates],
        achievement_probs: dict[str, float] | None = None,
        store_meta: dict[str, dict] | None = None,
    ) -> IncrementalProfitResult:
        """推算增量利润

        Args:
            baselines: {门店编码: 基线收入}
            targets: {门店编码: 目标收入（含基线+加压）}
            cost_rates: {门店编码: 成本比率}
            achievement_probs: {门店编码: 达成概率}，默认全部1.0
            store_meta: {门店编码: {"region": ..., "brand": ...}}

        Returns:
            IncrementalProfitResult
        """
        stores = {}
        probs = achievement_probs or {}

        for code, baseline in baselines.items():
            target = targets.get(code, baseline)
            rates = cost_rates.get(code, StoreCostRates(store_code=code))
            prob = probs.get(code, 1.0)

            detail = self._calc_store(code, baseline, target, rates, prob)
            stores[code] = detail

        # 汇总
        total_baseline = sum(d.baseline for d in stores.values())
        total_expected = sum(d.expected_revenue for d in stores.values())
        total_var_margin = sum(d.variable_margin for d in stores.values())
        total_net = sum(d.net_profit for d in stores.values())
        avg_m_var = (
            sum(d.m_variable * d.baseline for d in stores.values()) / total_baseline
            if total_baseline > 0 else 0
        )

        # 区域/品牌汇总
        region_summary = {}
        brand_summary = {}
        for code, detail in stores.items():
            meta = (store_meta or {}).get(code, {})
            region = meta.get("region", "未知")
            brand = meta.get("brand", "未知")

            if region not in region_summary:
                region_summary[region] = {"baseline": 0, "expected": 0, "net_profit": 0, "count": 0}
            region_summary[region]["baseline"] += detail.baseline
            region_summary[region]["expected"] += detail.expected_revenue
            region_summary[region]["net_profit"] += detail.net_profit
            region_summary[region]["count"] += 1

            if brand not in brand_summary:
                brand_summary[brand] = {"baseline": 0, "expected": 0, "net_profit": 0, "count": 0}
            brand_summary[brand]["baseline"] += detail.baseline
            brand_summary[brand]["expected"] += detail.expected_revenue
            brand_summary[brand]["net_profit"] += detail.net_profit
            brand_summary[brand]["count"] += 1

        result = IncrementalProfitResult(
            total_baseline=total_baseline,
            total_expected_revenue=round(total_expected, 0),
            total_variable_margin=round(total_var_margin, 0),
            total_net_profit=round(total_net, 0),
            avg_m_variable=round(avg_m_var, 4),
            store_count=len(stores),
            stores=stores,
            region_summary=region_summary,
            brand_summary=brand_summary,
        )

        logger.info(
            f"增量利润推算完成: {result.store_count} 家门店, "
            f"基线={total_baseline:,.0f}, "
            f"期望收入={total_expected:,.0f}, "
            f"变动边际利润={total_var_margin:,.0f}, "
            f"净利润={total_net:,.0f}, "
            f"平均m_variable={avg_m_var:.1%}"
        )

        return result

    def _calc_store(
        self,
        code: str,
        baseline: float,
        target: float,
        rates: StoreCostRates,
        achievement_prob: float,
    ) -> StoreProfitDetail:
        """计算单店增量利润

        公式链：
        期望收入 = 基线 + (目标 - 基线) × 达成概率
        牌价收入 = 期望收入 / 折扣率
        毛利 = 期望收入 × (1 - cost_rate/disc_rate)
        商场扣点 = 期望收入 × mall_fee_rate
        附加税 = 期望收入 × 附加税率(约1%)
        变动边际利润 = 毛利 - 商场扣点 - 附加税
        固定费用 = 基线 × (expense_rate - mall_fee_rate)
        管理费用 = 基线 × managing_exp_rate
        经营利润 = 变动边际利润 - 固定费用 - 管理费用
        平台返利 = 牌价收入 × rebate_rate
        净利润 = 经营利润 + 平台返利
        """
        extra = max(0, target - baseline)
        expected_revenue = baseline + extra * achievement_prob

        disc = max(rates.discount_rate, 0.30)
        list_price = expected_revenue / disc

        # 毛利
        gross_margin = 1.0 - rates.cost_rate / disc
        gross_profit = expected_revenue * gross_margin

        # 变动成本
        mall_fee = expected_revenue * rates.mall_fee_rate
        additional_tax = expected_revenue * 0.01  # 附加税约1%
        variable_margin = gross_profit - mall_fee - additional_tax

        # 固定成本（以基线为锚）
        fixed_expense = baseline * (rates.expense_rate - rates.mall_fee_rate)
        managing_expense = baseline * rates.managing_exp_rate
        nonoperating = baseline * rates.nonoperating_rate

        # 经营利润
        operating_profit = variable_margin - fixed_expense - managing_expense + nonoperating

        # 返利和佣金
        platform_rebate = list_price * rates.rebate_rate
        return_commission = expected_revenue * rates.return_commission_rate

        # 净利润
        net_profit = operating_profit + platform_rebate + return_commission

        return StoreProfitDetail(
            store_code=code,
            baseline=baseline,
            expected_revenue=round(expected_revenue, 0),
            extra_target=round(extra, 0),
            achievement_prob=achievement_prob,
            list_price=round(list_price, 0),
            gross_profit=round(gross_profit, 0),
            gross_margin=round(gross_margin, 4),
            mall_fee=round(mall_fee, 0),
            additional_tax=round(additional_tax, 0),
            variable_margin=round(variable_margin, 0),
            fixed_expense=round(fixed_expense, 0),
            managing_expense=round(managing_expense, 0),
            nonoperating=round(nonoperating, 0),
            operating_profit=round(operating_profit, 0),
            platform_rebate=round(platform_rebate, 0),
            return_commission=round(return_commission, 0),
            net_profit=round(net_profit, 0),
            m_variable=round(rates.m_variable, 4),
            m_full=round(rates.m_full, 4),
        )

    def compute_rates_from_financials(
        self,
        store_financials: dict[str, dict],
    ) -> dict[str, StoreCostRates]:
        """从财务数据计算门店成本比率

        Args:
            store_financials: {门店编码: {
                "revenue": 收入,
                "list_price": 牌价收入,
                "tax_cost": 含税成本,
                "mall_fee": 商场扣点,
                "operating_exp": 经营费用,
                "managing_exp": 管理费用,
                "nonoperating": 营业外收支,
                "platform_rebate": 平台返利,
                "return_commission": 退货佣金,
            }}

        Returns:
            {门店编码: StoreCostRates}
        """
        rates = {}
        for code, fin in store_financials.items():
            revenue = fin.get("revenue", 0)
            list_price = fin.get("list_price", revenue / 0.75)

            if revenue <= 0 or list_price <= 0:
                rates[code] = StoreCostRates(store_code=code)
                continue

            discount_rate = revenue / list_price
            cost_rate = fin.get("tax_cost", 0) / list_price
            mall_fee_rate = fin.get("mall_fee", 0) / revenue
            expense_rate = fin.get("operating_exp", 0) / revenue
            managing_exp_rate = fin.get("managing_exp", 0) / revenue
            nonoperating_rate = fin.get("nonoperating", 0) / revenue
            rebate_rate = fin.get("platform_rebate", 0) / list_price
            return_commission_rate = fin.get("return_commission", 0) / revenue

            rates[code] = StoreCostRates(
                store_code=code,
                discount_rate=round(min(1.0, max(0.3, discount_rate)), 4),
                cost_rate=round(min(0.80, max(0.20, cost_rate)), 4),
                mall_fee_rate=round(min(0.30, max(0, mall_fee_rate)), 4),
                expense_rate=round(min(0.50, max(0.05, expense_rate)), 4),
                managing_exp_rate=round(min(0.10, max(0, managing_exp_rate)), 4),
                nonoperating_rate=round(max(-0.05, nonoperating_rate), 4),
                rebate_rate=round(min(0.05, max(0, rebate_rate)), 4),
                return_commission_rate=round(min(0.05, max(0, return_commission_rate)), 4),
            )

        logger.info(f"从财务数据计算成本比率: {len(rates)} 家门店")
        return rates

    def apply_national_defaults(
        self,
        rates: dict[str, StoreCostRates],
    ) -> dict[str, StoreCostRates]:
        """对缺失字段应用全国兜底默认值"""
        for code, rate in rates.items():
            if rate.discount_rate == 0:
                rate.discount_rate = NATIONAL_DEFAULTS["discount_rate"]
            if rate.cost_rate == 0:
                rate.cost_rate = NATIONAL_DEFAULTS["cost_rate"]
            if rate.mall_fee_rate == 0:
                rate.mall_fee_rate = NATIONAL_DEFAULTS["mall_fee_rate"]
            if rate.expense_rate == 0:
                rate.expense_rate = NATIONAL_DEFAULTS["expense_rate"]
            if rate.managing_exp_rate == 0:
                rate.managing_exp_rate = NATIONAL_DEFAULTS["managing_exp_rate"]
        return rates

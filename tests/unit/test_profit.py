"""利润测算模块单元测试"""

import numpy as np
import pandas as pd
import pytest

from src.profit.profit_calculator import ProfitCalculator, StoreProfit, ProfitSummary
from src.profit.cost_estimator import CostEstimator, CostStructure
from src.profit.drill_down import DrillDownAnalyzer
from src.profit.profit_report import ProfitReportGenerator


class TestProfitCalculator:
    """利润计算器测试"""

    def test_calculate_basic(self):
        """基本利润计算"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000, "ST0002": 300_000}
        summary = calc.calculate(targets)

        assert summary.store_count == 2
        assert summary.total_revenue == 800_000
        assert summary.total_net_profit > 0
        assert summary.avg_gross_margin > 0
        assert summary.avg_net_margin > 0

    def test_calculate_with_custom_costs(self):
        """自定义成本结构"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        costs = {"ST0001": {"cogs_ratio": 0.40, "salary": 30_000, "rent": 20_000}}
        summary = calc.calculate(targets, costs)

        assert summary.store_count == 1
        sp = summary.store_profits["ST0001"]
        assert sp.cost_of_goods == 200_000  # 500k * 0.4
        assert sp.salary == 30_000

    def test_calculate_empty(self):
        """空输入"""
        calc = ProfitCalculator()
        summary = calc.calculate({})
        assert summary.store_count == 0
        assert summary.total_revenue == 0

    def test_to_dataframe(self):
        """转 DataFrame"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000, "ST0002": 300_000}
        summary = calc.calculate(targets)
        df = calc.to_dataframe(summary)

        assert len(df) == 2
        assert "门店编码" in df.columns
        assert "净利润" in df.columns

    def test_profit_summary_properties(self):
        """ProfitSummary 属性"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        summary = calc.calculate(targets)

        assert summary.profit_rate == 1.0  # 100% 盈利


class TestCostEstimator:
    """成本预估器测试"""

    def test_estimate_from_baselines(self):
        """基于基线预估成本"""
        estimator = CostEstimator()
        targets = {"ST0001": 600_000}
        baselines = {"ST0001": 500_000}
        costs = estimator.estimate_from_baselines(targets, baselines)

        assert "ST0001" in costs
        assert costs["ST0001"]["cogs_ratio"] > 0
        assert costs["ST0001"]["salary"] > 0

    def test_estimate_from_history(self):
        """基于历史预估成本"""
        estimator = CostEstimator()
        targets = {"ST0001": 600_000}
        history = {"ST0001": {"cogs_ratio": 0.42, "salary": 40_000}}
        costs = estimator.estimate_from_history(targets, history)

        assert costs["ST0001"]["cogs_ratio"] == 0.42
        assert costs["ST0001"]["salary"] == 40_000


class TestDrillDownAnalyzer:
    """下钻分析器测试"""

    def test_by_region(self):
        """按区域下钻"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000, "ST0002": 300_000, "ST0003": 400_000}
        summary = calc.calculate(targets)

        analyzer = DrillDownAnalyzer()
        region_map = {"ST0001": "华东", "ST0002": "华北", "ST0003": "华东"}
        result = analyzer.by_region(summary, region_map)

        assert result.dimension == "区域"
        assert "华东" in result.groups
        assert "华北" in result.groups
        assert result.groups["华东"]["门店数"] == 2

    def test_by_store_type(self):
        """按门店类型下钻"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000, "ST0002": 300_000}
        summary = calc.calculate(targets)

        analyzer = DrillDownAnalyzer()
        type_map = {"ST0001": "旗舰店", "ST0002": "标准店"}
        result = analyzer.by_store_type(summary, type_map)

        assert result.dimension == "门店类型"
        assert len(result.groups) == 2

    def test_top_bottom(self):
        """Top/Bottom 排行"""
        calc = ProfitCalculator()
        targets = {f"ST{i:04d}": 100_000 + i * 50_000 for i in range(1, 11)}
        summary = calc.calculate(targets)

        analyzer = DrillDownAnalyzer()
        ranking = analyzer.top_bottom(summary, n=3)

        assert len(ranking["top_n"]) == 3
        assert len(ranking["bottom_n"]) == 3


class TestProfitReportGenerator:
    """利润报告生成器测试"""

    def test_generate_summary_dict(self):
        """生成汇总字典"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        summary = calc.calculate(targets)

        gen = ProfitReportGenerator(calc)
        d = gen.generate_summary_dict(summary)

        assert "总收入" in d
        assert "总净利润" in d
        assert "门店总数" in d

    def test_generate_pnl_table(self):
        """生成 P&L 表"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        summary = calc.calculate(targets)

        gen = ProfitReportGenerator(calc)
        pnl = gen.generate_pnl_table(summary)

        assert len(pnl) > 0
        assert "项目" in pnl.columns
        assert "金额" in pnl.columns

    def test_generate_store_comparison(self):
        """生成门店对比表"""
        calc = ProfitCalculator()
        baseline = calc.calculate({"ST0001": 400_000})
        target = calc.calculate({"ST0001": 500_000})

        gen = ProfitReportGenerator(calc)
        df = gen.generate_store_comparison(baseline, target)

        assert len(df) == 1
        assert "基线收入" in df.columns
        assert "目标收入" in df.columns


class TestCostEstimatorFromRealData:
    """真实损益数据构建成本结构测试"""

    def _make_store_loss_df(self, store_codes: list[str], months: int = 3) -> pd.DataFrame:
        """构造模拟的门店损益 DataFrame"""
        rows = []
        dates = pd.date_range("2026-01-01", periods=months * 30, freq="D")
        for code in store_codes:
            for d in dates:
                rev = np.random.uniform(10_000, 30_000)
                rows.append({
                    "store_code": code,
                    "sale_date": d,
                    "actual_sales_pp": rev,
                    "actual_cost": rev * 0.42,
                    "actual_gross_profit": rev * 0.58,
                    "actual_salary": rev * 0.10,
                    "actual_social_fee": rev * 0.03,
                    "actual_operating_expense": rev * 0.25,
                    "actual_b_manage_expense": rev * 0.02,
                    "actual_mall_fee": rev * 0.03,
                    "actual_express": rev * 0.02,
                    "actual_other_fee": rev * 0.02,
                    "actual_decorate_fee": rev * 0.01,
                })
        return pd.DataFrame(rows)

    def test_from_store_loss_data_normal(self):
        """正常场景：从损益数据构建成本结构"""
        estimator = CostEstimator()
        df = self._make_store_loss_df(["ST0001", "ST0002"])
        targets = {"ST0001": 500_000, "ST0002": 400_000}

        result = estimator.from_store_loss_data(df, targets, months=3)

        assert "ST0001" in result
        assert "ST0002" in result
        assert result["ST0001"]["data_source"] == "real"
        assert result["ST0002"]["data_source"] == "real"
        assert 0.20 <= result["ST0001"]["cogs_ratio"] <= 0.80
        assert result["ST0001"]["salary"] > 0

    def test_from_store_loss_data_empty_df(self):
        """空 DataFrame 降级到默认值"""
        estimator = CostEstimator()
        targets = {"ST0001": 500_000}

        result = estimator.from_store_loss_data(pd.DataFrame(), targets)

        assert "ST0001" in result
        # 空数据时降级到 estimate_from_baselines，不会有 data_source="real"
        assert result["ST0001"]["cogs_ratio"] == estimator.default_cogs_ratio

    def test_from_store_loss_data_missing_store(self):
        """部分门店无数据时降级"""
        estimator = CostEstimator()
        df = self._make_store_loss_df(["ST0001"])
        targets = {"ST0001": 500_000, "ST0002": 400_000}

        result = estimator.from_store_loss_data(df, targets, months=3)

        assert result["ST0001"]["data_source"] == "real"
        # ST0002 无数据，降级到默认值
        assert "data_source" not in result["ST0002"] or result["ST0002"].get("data_source") != "real"


class TestProfitCalculatorWithRealCosts:
    """真实成本数据下的利润计算测试"""

    def test_data_source_field(self):
        """验证 data_source 字段传递"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        costs = {"ST0001": {
            "cogs_ratio": 0.42,
            "salary": 40_000,
            "rent": 25_000,
            "data_source": "real",
        }}
        summary = calc.calculate(targets, costs)

        sp = summary.store_profits["ST0001"]
        assert sp.data_source == "real"

    def test_data_source_default(self):
        """无 data_source 时默认为 default"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        summary = calc.calculate(targets)

        sp = summary.store_profits["ST0001"]
        assert sp.data_source == "default"

    def test_social_fee_field(self):
        """验证 social_fee 等扩展字段"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        costs = {"ST0001": {
            "cogs_ratio": 0.42,
            "salary": 40_000,
            "social_fee": 12_000,
            "mall_fee": 15_000,
        }}
        summary = calc.calculate(targets, costs)

        sp = summary.store_profits["ST0001"]
        assert sp.social_fee == 12_000
        assert sp.mall_fee == 15_000

    def test_to_dataframe_has_detail_columns(self):
        """验证 to_dataframe 包含明细列和数据来源"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        costs = {"ST0001": {"cogs_ratio": 0.42, "salary": 40_000, "data_source": "real"}}
        summary = calc.calculate(targets, costs)
        df = calc.to_dataframe(summary)

        assert "人工" in df.columns
        assert "租金" in df.columns
        assert "营销" in df.columns
        assert "物流" in df.columns
        assert "数据来源" in df.columns
        assert df.iloc[0]["数据来源"] == "real"


class TestProfitReportWithRealData:
    """真实数据下的报告测试"""

    def test_pnl_table_filled(self):
        """P&L 表分项数据不为空"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000, "ST0002": 300_000}
        summary = calc.calculate(targets)

        gen = ProfitReportGenerator(calc)
        pnl = gen.generate_pnl_table(summary)

        # 人工行应有金额
        salary_row = pnl[pnl["项目"].str.contains("人工")]
        assert not salary_row.empty
        assert salary_row.iloc[0]["金额"] != ""

        # 租金物业行应有金额
        rent_row = pnl[pnl["项目"].str.contains("租金物业")]
        assert not rent_row.empty
        assert rent_row.iloc[0]["金额"] != ""

    def test_pnl_table_with_real_data_source(self):
        """P&L 表显示数据来源"""
        calc = ProfitCalculator()
        targets = {"ST0001": 500_000}
        costs = {"ST0001": {"cogs_ratio": 0.42, "salary": 40_000, "data_source": "real"}}
        summary = calc.calculate(targets, costs)

        gen = ProfitReportGenerator(calc)
        pnl = gen.generate_pnl_table(summary)

        # 应有数据来源行
        source_rows = pnl[pnl["项目"].str.contains("数据来源")]
        assert len(source_rows) == 1
        assert "1/1" in source_rows.iloc[0]["项目"]

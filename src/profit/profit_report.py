"""利润报告生成器

生成结构化的利润测算报告，支持 DataFrame 和字典格式输出。
"""

import pandas as pd
from loguru import logger

from src.profit.profit_calculator import ProfitCalculator, ProfitSummary


class ProfitReportGenerator:
    """利润报告生成器"""

    def __init__(self, calculator: ProfitCalculator | None = None):
        self.calculator = calculator or ProfitCalculator()

    def generate_summary_dict(self, summary: ProfitSummary) -> dict:
        """生成汇总字典"""
        return {
            "总收入": round(summary.total_revenue, 0),
            "总采购成本": round(summary.total_cogs, 0),
            "总毛利": round(summary.total_gross_profit, 0),
            "平均毛利率": round(summary.avg_gross_margin, 4),
            "总运营费用": round(summary.total_operating_expense, 0),
            "总营业利润": round(summary.total_operating_profit, 0),
            "平均营业利润率": round(summary.avg_operating_margin, 4),
            "总税费": round(summary.total_tax, 0),
            "总净利润": round(summary.total_net_profit, 0),
            "平均净利率": round(summary.avg_net_margin, 4),
            "门店总数": summary.store_count,
            "盈利门店": summary.profitable_count,
            "亏损门店": summary.loss_count,
            "盈利占比": round(summary.profit_rate, 4),
        }

    def generate_pnl_table(self, summary: ProfitSummary) -> pd.DataFrame:
        """生成利润表（P&L）"""
        data = self.generate_summary_dict(summary)
        total_rev = data["总收入"]
        if total_rev <= 0:
            total_rev = 1  # 避免除零

        # 从门店明细汇总各分项
        total_salary = sum(sp.salary for sp in summary.store_profits.values())
        total_rent = sum(sp.rent for sp in summary.store_profits.values())
        total_marketing = sum(sp.marketing for sp in summary.store_profits.values())
        total_logistics = sum(sp.logistics for sp in summary.store_profits.values())
        total_property = sum(sp.property_fee for sp in summary.store_profits.values())
        total_depreciation = sum(sp.depreciation for sp in summary.store_profits.values())
        total_other = sum(sp.other_expense for sp in summary.store_profits.values())

        rows = [
            {"项目": "一、营业收入", "金额": data["总收入"], "占比": "100.0%"},
            {"项目": "减：采购成本", "金额": data["总采购成本"],
             "占比": f"{data['总采购成本']/total_rev*100:.1f}%"},
            {"项目": "二、毛利润", "金额": data["总毛利"],
             "占比": f"{data['平均毛利率']*100:.1f}%"},
            {"项目": "减：运营费用", "金额": data["总运营费用"],
             "占比": f"{data['总运营费用']/total_rev*100:.1f}%"},
            {"项目": "  其中：人工", "金额": round(total_salary, 0),
             "占比": f"{total_salary/total_rev*100:.1f}%"},
            {"项目": "        租金物业", "金额": round(total_rent + total_property, 0),
             "占比": f"{(total_rent + total_property)/total_rev*100:.1f}%"},
            {"项目": "        营销", "金额": round(total_marketing, 0),
             "占比": f"{total_marketing/total_rev*100:.1f}%"},
            {"项目": "        物流仓储", "金额": round(total_logistics, 0),
             "占比": f"{total_logistics/total_rev*100:.1f}%"},
            {"项目": "        折旧", "金额": round(total_depreciation, 0),
             "占比": f"{total_depreciation/total_rev*100:.1f}%"},
            {"项目": "        其他", "金额": round(total_other, 0),
             "占比": f"{total_other/total_rev*100:.1f}%"},
            {"项目": "三、营业利润", "金额": data["总营业利润"],
             "占比": f"{data['平均营业利润率']*100:.1f}%"},
            {"项目": "减：所得税", "金额": data["总税费"],
             "占比": f"{data['总税费']/total_rev*100:.1f}%"},
            {"项目": "四、净利润", "金额": data["总净利润"],
             "占比": f"{data['平均净利率']*100:.1f}%"},
        ]

        # 数据来源标记
        real_count = sum(1 for sp in summary.store_profits.values() if sp.data_source == "real")
        if real_count > 0:
            rows.append({
                "项目": f"[数据来源] {real_count}/{summary.store_count} 家使用真实损益数据",
                "金额": "", "占比": "",
            })

        return pd.DataFrame(rows)

    def generate_store_comparison(
        self, baseline_summary: ProfitSummary, target_summary: ProfitSummary
    ) -> pd.DataFrame:
        """生成基线 vs 目标对比表"""
        rows = []
        for code in baseline_summary.store_profits:
            base = baseline_summary.store_profits[code]
            target = target_summary.store_profits.get(code)
            if not target:
                continue
            rows.append({
                "门店编码": code,
                "基线收入": round(base.revenue, 0),
                "目标收入": round(target.revenue, 0),
                "收入增长": f"{(target.revenue - base.revenue) / base.revenue:.1%}" if base.revenue > 0 else "N/A",
                "基线净利": round(base.net_profit, 0),
                "目标净利": round(target.net_profit, 0),
                "净利增长": round(target.net_profit - base.net_profit, 0),
            })
        return pd.DataFrame(rows)

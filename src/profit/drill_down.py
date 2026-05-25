"""下钻分析器

按不同维度对利润进行下钻分析：
  - 按品类（鞋/服/包/配件）
  - 按渠道（直营/加盟/商场）
  - 按区域（大区/小区/城市）
  - 按门店类型（旗舰店/标准店/奥莱）
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.profit.profit_calculator import ProfitSummary, StoreProfit


@dataclass
class DrillDownResult:
    """下钻分析结果"""
    dimension: str          # 下钻维度
    groups: dict[str, dict]  # {分组名: 指标}

    def to_dataframe(self) -> pd.DataFrame:
        rows = []
        for name, metrics in self.groups.items():
            row = {"分组": name}
            row.update(metrics)
            rows.append(row)
        return pd.DataFrame(rows)


class DrillDownAnalyzer:
    """下钻分析器

    使用方式：
        analyzer = DrillDownAnalyzer()
        result = analyzer.by_region(profit_summary, store_region_map)
    """

    def by_region(
        self,
        summary: ProfitSummary,
        store_region_map: dict[str, str],
    ) -> DrillDownResult:
        """按区域下钻"""
        groups = {}
        for store_code, profit in summary.store_profits.items():
            region = store_region_map.get(store_code, "未知")
            if region not in groups:
                groups[region] = {
                    "门店数": 0, "收入": 0, "毛利": 0, "运营费用": 0,
                    "营业利润": 0, "净利润": 0,
                }
            g = groups[region]
            g["门店数"] += 1
            g["收入"] += profit.revenue
            g["毛利"] += profit.gross_profit
            g["运营费用"] += profit.operating_expense
            g["营业利润"] += profit.operating_profit
            g["净利润"] += profit.net_profit

        # 计算比率
        for g in groups.values():
            g["毛利率"] = g["毛利"] / g["收入"] if g["收入"] > 0 else 0
            g["营业利润率"] = g["营业利润"] / g["收入"] if g["收入"] > 0 else 0
            g["净利率"] = g["净利润"] / g["收入"] if g["收入"] > 0 else 0

        return DrillDownResult(dimension="区域", groups=groups)

    def by_store_type(
        self,
        summary: ProfitSummary,
        store_type_map: dict[str, str],
    ) -> DrillDownResult:
        """按门店类型下钻"""
        groups = {}
        for store_code, profit in summary.store_profits.items():
            stype = store_type_map.get(store_code, "标准店")
            if stype not in groups:
                groups[stype] = {
                    "门店数": 0, "收入": 0, "毛利": 0, "净利润": 0,
                    "平均坪效": 0, "_count_sqm": 0,
                }
            g = groups[stype]
            g["门店数"] += 1
            g["收入"] += profit.revenue
            g["毛利"] += profit.gross_profit
            g["净利润"] += profit.net_profit

        for g in groups.values():
            g["毛利率"] = g["毛利"] / g["收入"] if g["收入"] > 0 else 0
            g["净利率"] = g["净利润"] / g["收入"] if g["收入"] > 0 else 0

        return DrillDownResult(dimension="门店类型", groups=groups)

    def by_channel(
        self,
        summary: ProfitSummary,
        store_channel_map: dict[str, str],
    ) -> DrillDownResult:
        """按渠道下钻"""
        groups = {}
        for store_code, profit in summary.store_profits.items():
            channel = store_channel_map.get(store_code, "直营")
            if channel not in groups:
                groups[channel] = {
                    "门店数": 0, "收入": 0, "毛利": 0,
                    "营业利润": 0, "净利润": 0,
                }
            g = groups[channel]
            g["门店数"] += 1
            g["收入"] += profit.revenue
            g["毛利"] += profit.gross_profit
            g["营业利润"] += profit.operating_profit
            g["净利润"] += profit.net_profit

        for g in groups.values():
            g["毛利率"] = g["毛利"] / g["收入"] if g["收入"] > 0 else 0
            g["营业利润率"] = g["营业利润"] / g["收入"] if g["收入"] > 0 else 0

        return DrillDownResult(dimension="渠道", groups=groups)

    def top_bottom(
        self,
        summary: ProfitSummary,
        n: int = 5,
    ) -> dict[str, pd.DataFrame]:
        """Top/Bottom 门店排行"""
        df = pd.DataFrame([
            {
                "门店编码": code,
                "收入": p.revenue,
                "净利润": p.net_profit,
                "净利率": p.net_margin,
            }
            for code, p in summary.store_profits.items()
        ])

        return {
            "top_n": df.nlargest(n, "净利润").reset_index(drop=True),
            "bottom_n": df.nsmallest(n, "净利润").reset_index(drop=True),
        }

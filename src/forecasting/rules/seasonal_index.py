"""季节指数计算

计算品牌 × 区域 × 日历月的季节指数，含阻尼处理。
排除春节月数据后计算原始指数，再应用阻尼因子。
"""

from dataclasses import dataclass, field

import pandas as pd

from src.forecasting.rules.lunar_calendar import LunarCalendar


@dataclass
class SeasonalIndex:
    """单个品牌×区域的季节指数"""
    brand: str
    region: str
    raw_indices: dict[int, float] = field(default_factory=dict)      # {月: 原始指数}
    damped_indices: dict[int, float] = field(default_factory=dict)   # {月: 阻尼指数}
    damping_factor: float = 0.50
    data_months: int = 0  # 参与计算的月份数

    def get_factor(self, month: int, damped: bool = True) -> float:
        """获取指定月份的季节因子

        Args:
            month: 月份 (1-12)
            damped: 是否使用阻尼指数（默认 True）

        Returns:
            季节因子，如果没有数据返回 1.0
        """
        indices = self.damped_indices if damped else self.raw_indices
        return indices.get(month, 1.0)


@dataclass
class SeasonalIndexTable:
    """季节指数表（所有品牌×区域组合）"""
    indices: dict[tuple[str, str], SeasonalIndex] = field(default_factory=dict)

    def get_factor(
        self,
        brand: str,
        region: str,
        month: int,
        damped: bool = True,
    ) -> float:
        """获取指定品牌×区域×月份的季节因子

        Args:
            brand: 品牌
            region: 区域
            month: 月份
            damped: 是否使用阻尼指数

        Returns:
            季节因子，如果没有该品牌×区域的指数返回 1.0
        """
        key = (brand, region)
        if key not in self.indices:
            # 尝试只用品牌匹配
            for (b, r), idx in self.indices.items():
                if b == brand:
                    return idx.get_factor(month, damped)
            return 1.0
        return self.indices[key].get_factor(month, damped)

    def get_all_brands(self) -> list[str]:
        """获取所有品牌列表"""
        return list({b for b, _ in self.indices.keys()})

    def get_all_regions(self) -> list[str]:
        """获取所有区域列表"""
        return list({r for _, r in self.indices.keys()})


class SeasonalIndexCalculator:
    """季节指数计算器

    计算流程：
    1. 排除春节月数据
    2. 按品牌×区域×日历月汇总历史均值
    3. 原始季节指数 = 该月均值 / 全部月均值
    4. 阻尼季节指数 = 1 + (原始 - 1) × 阻尼因子

    使用方式：
        calc = SeasonalIndexCalculator()
        table = calc.calculate(monthly_metrics_df, stores_df)
        factor = table.get_factor("品牌A", "华东", 12)
    """

    def __init__(
        self,
        lunar_calendar: LunarCalendar | None = None,
        damping_factor: float = 0.50,
    ):
        self._lunar = lunar_calendar or LunarCalendar()
        self._damping_factor = damping_factor

    def calculate(
        self,
        monthly_metrics_df: pd.DataFrame,
        stores_df: pd.DataFrame,
    ) -> SeasonalIndexTable:
        """计算季节指数表

        Args:
            monthly_metrics_df: 月度指标 DataFrame
                必需列：store_code, year_month, sales_amount
            stores_df: 门店主数据 DataFrame
                必需列：store_code, brand, region

        Returns:
            SeasonalIndexTable
        """
        if monthly_metrics_df.empty or stores_df.empty:
            return SeasonalIndexTable()

        # 合并品牌和区域信息
        merged = monthly_metrics_df.merge(
            stores_df[["store_code", "brand", "region"]],
            on="store_code",
            how="left",
        )

        # 解析 year_month 为年和月
        merged = self._parse_year_month(merged)

        # 排除春节月
        merged = self._exclude_spring_festival(merged)

        if merged.empty:
            return SeasonalIndexTable()

        # 按品牌×区域×月汇总
        grouped = merged.groupby(["brand", "region", "month"])["sales_amount"].mean()
        overall = merged.groupby(["brand", "region"])["sales_amount"].mean()

        indices = {}

        for (brand, region), group in grouped.groupby(level=[0, 1]):
            overall_mean = overall.get((brand, region), 0)
            if overall_mean <= 0:
                continue

            raw_indices = {}
            damped_indices = {}

            for month in range(1, 13):
                month_mean = group.get((brand, region, month))
                if month_mean is not None and pd.notna(month_mean):
                    raw = float(month_mean / overall_mean)
                    damped = 1.0 + (raw - 1.0) * self._damping_factor
                    raw_indices[month] = round(raw, 4)
                    damped_indices[month] = round(damped, 4)

            if raw_indices:
                data_months = len(raw_indices)
                indices[(brand, region)] = SeasonalIndex(
                    brand=brand,
                    region=region,
                    raw_indices=raw_indices,
                    damped_indices=damped_indices,
                    damping_factor=self._damping_factor,
                    data_months=data_months,
                )

        return SeasonalIndexTable(indices=indices)

    def _parse_year_month(self, df: pd.DataFrame) -> pd.DataFrame:
        """解析 year_month 列，增加 month 列"""
        df = df.copy()
        if "month" not in df.columns:
            # year_month 格式可能是 "2024-01" 或 datetime
            if df["year_month"].dtype == "object":
                # 字符串格式
                df["month"] = df["year_month"].str[-2:].astype(int)
            else:
                # datetime 格式
                df["month"] = pd.to_datetime(df["year_month"]).dt.month
        return df

    def _exclude_spring_festival(self, df: pd.DataFrame) -> pd.DataFrame:
        """排除春节月数据"""
        if "year" not in df.columns:
            # 从 year_month 提取年份
            if df["year_month"].dtype == "object":
                df["year"] = df["year_month"].str[:4].astype(int)
            else:
                df["year"] = pd.to_datetime(df["year_month"]).dt.year

        # 标记春节月
        mask = df.apply(
            lambda row: not self._lunar.is_spring_festival_month(
                int(row["year"]), int(row["month"])
            ),
            axis=1,
        )
        return df[mask]

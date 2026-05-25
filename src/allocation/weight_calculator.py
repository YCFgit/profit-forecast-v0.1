"""门店能力权重计算器

根据多维度指标计算各门店的承压能力权重。
权重越大 → 分配越多的承压额。

维度与默认权重：
  - 历史利润能力 (historical_profit): 35%
  - 坪效 (sales_per_sqm):            25%
  - 商圈等级 (commercial_tier):       20%
  - 门店面积 (store_area):            10%
  - 增长趋势 (growth_trend):          10%
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger


# 商圈等级映射分数
COMMERCIAL_TIER_SCORES = {
    "S": 1.0,   # 顶级商圈
    "A": 0.85,  # 优质商圈
    "B": 0.65,  # 良好商圈
    "C": 0.45,  # 一般商圈
    "D": 0.25,  # 边缘商圈
}

# 城市等级映射分数
CITY_LEVEL_SCORES = {
    "一线": 1.0,
    "新一线": 0.85,
    "二线": 0.70,
    "三线": 0.55,
    "四线": 0.40,
    "五线": 0.25,
}


@dataclass
class WeightConfig:
    """权重配置"""
    historical_profit: float = 0.35   # 历史利润能力
    sales_per_sqm: float = 0.25       # 坪效
    commercial_tier: float = 0.20     # 商圈等级
    store_area: float = 0.10          # 门店面积
    growth_trend: float = 0.10        # 增长趋势

    def validate(self) -> bool:
        total = (
            self.historical_profit + self.sales_per_sqm +
            self.commercial_tier + self.store_area + self.growth_trend
        )
        if abs(total - 1.0) > 0.001:
            logger.warning(f"权重总和 {total:.3f} ≠ 1.0，将自动归一化")
            return False
        return True

    def normalize(self) -> "WeightConfig":
        """归一化权重使总和为 1"""
        total = (
            self.historical_profit + self.sales_per_sqm +
            self.commercial_tier + self.store_area + self.growth_trend
        )
        if total == 0:
            return WeightConfig()
        return WeightConfig(
            historical_profit=self.historical_profit / total,
            sales_per_sqm=self.sales_per_sqm / total,
            commercial_tier=self.commercial_tier / total,
            store_area=self.store_area / total,
            growth_trend=self.growth_trend / total,
        )


@dataclass
class StoreProfile:
    """门店画像（单店）"""
    store_code: str
    historical_profit: float = 0.0    # 近 12 个月平均利润
    sales_per_sqm: float = 0.0        # 坪效
    commercial_tier: str = "C"         # 商圈等级
    city_level: str = "二线"           # 城市等级
    store_area: float = 100.0          # 门店面积
    growth_rate: float = 0.0           # 近 3 个月增长率
    opening_months: int = 12           # 开业月数
    baseline_sales: float = 0.0        # 基线销售额


class WeightCalculator:
    """门店能力权重计算器

    使用方式：
        calc = WeightCalculator()
        weights = calc.calculate(store_profiles)
    """

    def __init__(self, config: WeightConfig | None = None):
        self.config = (config or WeightConfig()).normalize()

    def calculate(
        self,
        store_profiles: dict[str, StoreProfile],
    ) -> dict[str, float]:
        """计算各门店的承压权重

        Args:
            store_profiles: {门店编码: 门店画像}

        Returns:
            {门店编码: 权重}，权重之和 = 1.0
        """
        if not store_profiles:
            return {}

        # Step 1: 提取各维度原始值
        raw_data = {}
        for code, profile in store_profiles.items():
            raw_data[code] = {
                "historical_profit": profile.historical_profit,
                "sales_per_sqm": profile.sales_per_sqm,
                "commercial_tier": self._tier_to_score(profile.commercial_tier),
                "store_area": profile.store_area,
                "growth_trend": max(0, profile.growth_rate),  # 负增长按 0 算
            }

        df = pd.DataFrame(raw_data).T

        # Step 2: Min-Max 归一化到 [0, 1]
        normalized = pd.DataFrame(index=df.index)
        for col in df.columns:
            col_min = df[col].min()
            col_max = df[col].max()
            if col_max - col_min == 0:
                normalized[col] = 0.5  # 全部相同则给中间值
            else:
                normalized[col] = (df[col] - col_min) / (col_max - col_min)

        # Step 3: 加权求和
        weights_raw = {}
        for code in normalized.index:
            score = 0.0
            score += normalized.loc[code, "historical_profit"] * self.config.historical_profit
            score += normalized.loc[code, "sales_per_sqm"] * self.config.sales_per_sqm
            score += normalized.loc[code, "commercial_tier"] * self.config.commercial_tier
            score += normalized.loc[code, "store_area"] * self.config.store_area
            score += normalized.loc[code, "growth_trend"] * self.config.growth_trend
            weights_raw[code] = score

        # Step 4: 归一化使权重之和 = 1
        total = sum(weights_raw.values())
        if total == 0:
            n = len(weights_raw)
            return {code: 1.0 / n for code in weights_raw}

        weights = {code: val / total for code, val in weights_raw.items()}

        logger.info(
            f"权重计算完成: {len(weights)} 家门店, "
            f"最高={max(weights.values()):.4f}({max(weights, key=weights.get)}), "
            f"最低={min(weights.values()):.4f}({min(weights, key=weights.get)})"
        )

        return weights

    def calculate_with_detail(
        self,
        store_profiles: dict[str, StoreProfile],
    ) -> pd.DataFrame:
        """计算权重并返回详细分值

        Returns:
            DataFrame with columns: store_code, 各维度分值, 综合权重
        """
        if not store_profiles:
            return pd.DataFrame()

        raw_data = {}
        for code, profile in store_profiles.items():
            raw_data[code] = {
                "store_code": code,
                "raw_profit": profile.historical_profit,
                "raw_sqm": profile.sales_per_sqm,
                "raw_tier": self._tier_to_score(profile.commercial_tier),
                "raw_area": profile.store_area,
                "raw_growth": max(0, profile.growth_rate),
            }

        df = pd.DataFrame(raw_data).T
        df.index = range(len(df))

        # 归一化
        raw_cols = ["raw_profit", "raw_sqm", "raw_tier", "raw_area", "raw_growth"]
        for col in raw_cols:
            col_min = df[col].min()
            col_max = df[col].max()
            if col_max - col_min == 0:
                df[f"norm_{col[4:]}"] = 0.5
            else:
                df[f"norm_{col[4:]}"] = (df[col] - col_min) / (col_max - col_min)

        # 加权分
        df["score"] = (
            df["norm_profit"] * self.config.historical_profit +
            df["norm_sqm"] * self.config.sales_per_sqm +
            df["norm_tier"] * self.config.commercial_tier +
            df["norm_area"] * self.config.store_area +
            df["norm_growth"] * self.config.growth_trend
        )

        # 归一化权重
        total = df["score"].sum()
        df["weight"] = df["score"] / total if total > 0 else 1.0 / len(df)

        # 加上维度名称
        df["tier_label"] = df["store_code"].map(
            lambda c: store_profiles[c].commercial_tier
        )

        return df[[
            "store_code", "tier_label",
            "raw_profit", "raw_sqm", "raw_area", "raw_growth",
            "norm_profit", "norm_sqm", "norm_tier", "norm_area", "norm_growth",
            "score", "weight",
        ]].sort_values("weight", ascending=False).reset_index(drop=True)

    @staticmethod
    def _tier_to_score(tier: str) -> float:
        """商圈等级转分数"""
        return COMMERCIAL_TIER_SCORES.get(tier.upper(), 0.45)

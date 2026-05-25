"""品牌季节折扣矩阵

从 POS 数据构建按品牌、品牌季节、上市月数的折扣衰减曲线。
"""

import pandas as pd
from loguru import logger


class BrandSeasonMatrix:
    """品牌季节折扣矩阵"""

    def __init__(self, pos_df: pd.DataFrame):
        self.pos_df = pos_df
        self._matrix = None

    def get_matrix(self) -> pd.DataFrame:
        if self._matrix is None:
            self._build_matrix()
        return self._matrix

    def get_decay_curve(self, brand_code: str, season_type: str) -> pd.DataFrame:
        matrix = self.get_matrix()
        curve = matrix[
            (matrix["brand_code"] == brand_code) &
            (matrix["season_type"] == season_type)
        ][["months_since_launch", "avg_discount_rate"]].sort_values("months_since_launch")
        return curve

    def get_season_correction(self, brand_code: str, season_type: str,
                               current_month: int, last_year_month: int) -> float:
        curve = self.get_decay_curve(brand_code, season_type)
        if curve.empty:
            return 1.0
        current_rate = curve[curve["months_since_launch"] == current_month]["avg_discount_rate"]
        last_year_rate = curve[curve["months_since_launch"] == last_year_month]["avg_discount_rate"]
        if current_rate.empty or last_year_rate.empty:
            return 1.0
        return float(current_rate.iloc[0] / last_year_rate.iloc[0])

    def _build_matrix(self):
        df = self.pos_df.copy()
        df = df[(df["discount_rate"] > 0) & (df["discount_rate"] <= 1)]
        self._matrix = df.groupby(
            ["brand_code", "brand_name", "season_type", "months_since_launch"]
        ).agg(
            avg_discount_rate=("discount_rate", "mean"),
            discount_std=("discount_rate", "std"),
            sample_count=("discount_rate", "count"),
        ).reset_index()
        self._matrix["discount_std"] = self._matrix["discount_std"].fillna(0)
        logger.info(f"品牌季节折扣矩阵构建完成: {len(self._matrix)} 条记录")

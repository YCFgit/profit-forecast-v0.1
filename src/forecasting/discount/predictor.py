"""折扣率预测器

结合同比折扣趋势 + 品牌季节修正系数，预测未来月度折扣率。
"""

import pandas as pd
from loguru import logger

from src.forecasting.discount.brand_season_matrix import BrandSeasonMatrix


class DiscountPredictor:
    """折扣率预测器"""

    def __init__(self, pos_df: pd.DataFrame):
        self.pos_df = pos_df
        self.matrix = BrandSeasonMatrix(pos_df)
        self._monthly_trend = None

    def predict(self, brand_code: str, months_ahead: int = 3) -> pd.DataFrame:
        yoy_trend = self._get_yoy_trend(brand_code)
        season_correction = self._get_season_correction(brand_code)

        forecasts = []
        for i in range(1, months_ahead + 1):
            yoy_base = yoy_trend.get(i, 0.80)
            correction = season_correction.get(i, 1.0)
            forecast_rate = yoy_base * correction
            forecast_rate = max(0.10, min(1.0, forecast_rate))

            forecasts.append({
                "month_offset": i,
                "forecast_discount_rate": round(forecast_rate, 4),
                "yoy_base": round(yoy_base, 4),
                "season_correction": round(correction, 4),
                "method": "yoy_season_blend",
                "confidence": round(0.8 - i * 0.05, 2),
            })

        result = pd.DataFrame(forecasts)
        logger.info(f"折扣预测完成: brand={brand_code}, {months_ahead} 个月")
        return result

    def _get_yoy_trend(self, brand_code: str) -> dict:
        df = self.pos_df[self.pos_df["brand_code"] == brand_code]
        if df.empty:
            return {}
        monthly = df.groupby("year_month")["discount_rate"].mean()
        trend = {}
        for i, rate in enumerate(monthly.tail(12).values, 1):
            trend[i] = rate
        return trend

    def _get_season_correction(self, brand_code: str) -> dict:
        matrix_df = self.matrix.get_matrix()
        brand_matrix = matrix_df[matrix_df["brand_code"] == brand_code]
        if brand_matrix.empty:
            return {}
        correction = {}
        rates = brand_matrix.groupby("months_since_launch")["avg_discount_rate"].mean()
        if len(rates) >= 2:
            first_rate = rates.iloc[0]
            for month_offset, rate in rates.items():
                correction[month_offset] = rate / first_rate if first_rate > 0 else 1.0
        return correction

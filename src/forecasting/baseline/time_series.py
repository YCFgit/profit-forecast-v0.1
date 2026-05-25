"""时间序列预处理与基线预估管线

完整的数据预处理流程：
  原始数据 → 质量检查 → 异常值剔除 → 季节性分解 → 趋势提取 → 基线输出
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from loguru import logger

from src.forecasting.baseline.outlier_detector import OutlierDetector, OutlierResult
from src.forecasting.baseline.seasonal_decompose import SeasonalDecomposer, SeasonalResult


@dataclass
class PreprocessedSeries:
    """预处理后的时间序列"""
    store_code: str
    raw_series: pd.Series               # 原始序列
    clean_series: pd.Series             # 清洗后序列（异常值已处理）
    monthly_series: pd.Series           # 月度聚合序列
    outlier_result: OutlierResult       # 异常检测结果
    seasonal_result: SeasonalResult     # 季节性分解结果
    has_enough_data: bool = True        # 数据是否充足

    @property
    def monthly_clean(self) -> pd.Series:
        """去季节性后的月度序列"""
        result = self.monthly_series.copy()
        for i, dt in enumerate(result.index):
            month = dt.month if hasattr(dt, 'month') else pd.to_datetime(dt).month
            factor = self.seasonal_result.get_factor(month)
            if factor != 0:
                result.iloc[i] = result.iloc[i] / factor
        return result


@dataclass
class BaselineResult:
    """单店基线预估结果"""
    store_code: str
    predicted_sales: float              # 预测销售额
    predicted_profit: float             # 预测利润
    confidence_interval: tuple[float, float]  # 置信区间
    growth_rate: float                  # 增长率
    seasonal_factor: float              # 季节因子
    model_name: str                     # 使用的模型
    accuracy_mape: float                # 回测 MAPE
    data_quality_score: float           # 数据质量分 (0-1)


class TimeSeriesPreprocessor:
    """时间序列预处理器

    将原始的日/月销售数据清洗、分解为可建模的干净序列。

    使用方式：
        preprocessor = TimeSeriesPreprocessor()
        result = preprocessor.preprocess(store_code, daily_sales_df)
    """

    def __init__(
        self,
        outlier_detector: OutlierDetector | None = None,
        seasonal_decomposer: SeasonalDecomposer | None = None,
        min_monthly_points: int = 6,
    ):
        self.outlier_detector = outlier_detector or OutlierDetector()
        self.seasonal_decomposer = seasonal_decomposer or SeasonalDecomposer()
        self.min_monthly_points = min_monthly_points

    def preprocess(
        self,
        store_code: str,
        daily_sales: pd.DataFrame,
        date_col: str = "sale_date",
        value_col: str = "sales_amount",
        closure_periods: list[tuple[date, date]] | None = None,
    ) -> PreprocessedSeries:
        """预处理单店的时间序列

        Args:
            store_code: 门店编码
            daily_sales: 日销售数据（需包含日期和金额列）
            date_col: 日期列名
            value_col: 金额列名
            closure_periods: 闭店期间

        Returns:
            PreprocessedSeries
        """
        logger.info(f"[{store_code}] 开始预处理")

        # Step 1: 数据质量检查
        df = daily_sales.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)

        # 按日期聚合（可能有多个品类/品牌的日数据）
        daily_agg = df.groupby(date_col)[value_col].sum()

        if len(daily_agg) < 30:
            logger.warning(f"[{store_code}] 日数据不足 30 天")

        # Step 2: 异常值检测
        clean_daily, outlier_result = self.outlier_detector.detect(
            daily_agg, closure_periods=closure_periods
        )

        # Step 3: 聚合到月度
        clean_daily.index = pd.to_datetime(clean_daily.index)
        monthly = clean_daily.resample("MS").sum()
        # 去掉不完整的月份（首尾）
        if len(monthly) > 2:
            monthly = monthly.iloc[1:-1]

        has_enough = len(monthly.dropna()) >= self.min_monthly_points

        # Step 4: 季节性分解
        if has_enough:
            seasonal_result = self.seasonal_decomposer.decompose(monthly.dropna())
        else:
            seasonal_result = SeasonalResult(
                seasonal_index={i: 1.0 for i in range(1, 13)},
                trend=monthly,
                residual=pd.Series(0, index=monthly.index),
                strength=0.0,
            )

        result = PreprocessedSeries(
            store_code=store_code,
            raw_series=daily_agg,
            clean_series=clean_daily,
            monthly_series=monthly,
            outlier_result=outlier_result,
            seasonal_result=seasonal_result,
            has_enough_data=has_enough,
        )

        logger.info(
            f"[{store_code}] 预处理完成: {len(monthly)}个月数据, "
            f"季节强度={seasonal_result.strength:.2f}, "
            f"数据充足={'是' if has_enough else '否'}"
        )

        return result


def prepare_store_monthly_data(
    daily_sales: pd.DataFrame,
    store_code: str,
    value_col: str = "sales_amount",
    date_col: str = "sale_date",
) -> pd.Series:
    """从日销售数据提取单店月度序列

    快捷函数，适用于不需要完整预处理的场景。
    """
    df = daily_sales.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    if "store_code" in df.columns:
        df = df[df["store_code"] == store_code]

    monthly = df.set_index(date_col).resample("MS")[value_col].sum()
    return monthly[monthly > 0]

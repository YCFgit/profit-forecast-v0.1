"""业务规则预估引擎

基于门店分类、季节指数、春节月处理的规则化预估方案。
替代原有的 ARIMA/Prophet/指数平滑三模型自动选择。
"""

from src.forecasting.rules.lunar_calendar import LunarCalendar
from src.forecasting.rules.store_classifier import (
    StoreCategory,
    StoreClassification,
    ClassificationResult,
    StoreClassifier,
)
from src.forecasting.rules.seasonal_index import (
    SeasonalIndex,
    SeasonalIndexTable,
    SeasonalIndexCalculator,
)
from src.forecasting.rules.spring_festival import SpringFestivalEstimator
from src.forecasting.rules.large_store_estimator import LargeStoreEstimator
from src.forecasting.rules.small_store_estimator import SmallStoreEstimator
from src.forecasting.rules.new_store_estimator import NewStoreEstimator
from src.forecasting.rules.virtual_store_estimator import VirtualStoreEstimator
from src.forecasting.rules.temp_store_estimator import TempStoreEstimator
from src.forecasting.rules.closing_store_estimator import ClosingStoreEstimator

__all__ = [
    "LunarCalendar",
    "StoreCategory",
    "StoreClassification",
    "ClassificationResult",
    "StoreClassifier",
    "SeasonalIndex",
    "SeasonalIndexTable",
    "SeasonalIndexCalculator",
    "SpringFestivalEstimator",
    "LargeStoreEstimator",
    "SmallStoreEstimator",
    "NewStoreEstimator",
    "VirtualStoreEstimator",
    "TempStoreEstimator",
    "ClosingStoreEstimator",
]

"""基线预估模块

业务规则预估引擎（v2）：
  门店分类 → 季节指数 → 分类预估 → 基线输出

核心类（v2 规则引擎）：
  - BaselineEngine: 引擎总调度
  - StoreClassifier: 门店 6 分类
  - SeasonalIndexCalculator: 季节指数计算
  - LunarCalendar: 春节月判定

旧模块（v1 统计模型，已废弃，不再调用）：
  - ModelSelector / ARIMAModel / ProphetModel / ExponentialSmoothingModel
"""

# v2 业务规则引擎（当前使用）
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
from src.forecasting.rules.baseline_engine import (
    BaselineEngine,
    BaselineEngineResult,
    StoreEstimateDetail,
)

# 精度评估（仍然可用）
from src.forecasting.evaluation.accuracy_metrics import (
    AccuracyResult,
    calc_mae,
    calc_mape,
    calc_rmse,
    calc_r2,
    evaluate,
)

# 预处理工具（仍然可用）
from src.forecasting.baseline.outlier_detector import OutlierDetector, OutlierResult
from src.forecasting.baseline.seasonal_decompose import (
    SeasonalDecomposer,
    SeasonalResult,
    get_shoe_seasonal_default,
)
from src.forecasting.baseline.time_series import (
    BaselineResult,
    PreprocessedSeries,
    TimeSeriesPreprocessor,
    prepare_store_monthly_data,
)

__all__ = [
    # v2 规则引擎
    "LunarCalendar",
    "StoreCategory", "StoreClassification", "ClassificationResult", "StoreClassifier",
    "SeasonalIndex", "SeasonalIndexTable", "SeasonalIndexCalculator",
    "BaselineEngine", "BaselineEngineResult", "StoreEstimateDetail",
    # 精度评估
    "AccuracyResult", "calc_mape", "calc_rmse", "calc_mae", "calc_r2", "evaluate",
    # 预处理
    "OutlierDetector", "OutlierResult",
    "SeasonalDecomposer", "SeasonalResult", "get_shoe_seasonal_default",
    "TimeSeriesPreprocessor", "PreprocessedSeries", "BaselineResult",
    "prepare_store_monthly_data",
]

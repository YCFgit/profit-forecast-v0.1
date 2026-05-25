"""基线预估引擎总调度

整合门店分类、季节指数、各类预估器，输出统一的基线预估结果。
替代原有的 ModelSelector + BaselineAgent.forecast() 流程。
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.forecasting.rules.lunar_calendar import LunarCalendar
from src.forecasting.rules.store_classifier import (
    StoreCategory,
    StoreClassifier,
    ClassificationResult,
)
from src.forecasting.rules.seasonal_index import SeasonalIndexCalculator, SeasonalIndexTable
from src.forecasting.rules.large_store_estimator import LargeStoreEstimator, LargeStoreEstimate
from src.forecasting.rules.small_store_estimator import SmallStoreEstimator, SmallStoreEstimate
from src.forecasting.rules.new_store_estimator import NewStoreEstimator, NewStoreEstimate
from src.forecasting.rules.virtual_store_estimator import VirtualStoreEstimator, VirtualStoreEstimate
from src.forecasting.rules.temp_store_estimator import TempStoreEstimator, TempStoreEstimate
from src.forecasting.rules.closing_store_estimator import ClosingStoreEstimator, ClosingStoreEstimate
from src.forecasting.rules.spring_festival import SpringFestivalEstimator, SpringFestivalEstimate


@dataclass
class StoreEstimateDetail:
    """单店预估详情"""
    store_code: str
    category: StoreCategory
    estimated_sales: float
    mechanism: str
    confidence: str = "medium"
    seasonal_index: float = 1.0
    des_seasonal_sales: float = 0.0
    brand: str = ""
    region: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class BaselineEngineResult:
    """引擎输出结果

    baselines: dict[str, float] — 核心输出，与下游兼容
    model_info: dict[str, dict] — 模型信息，用于 API 返回
    classifications: ClassificationResult — 分类结果
    seasonal_table: SeasonalIndexTable — 季节指数表
    """
    baselines: dict[str, float]
    model_info: dict[str, dict]
    classifications: ClassificationResult
    seasonal_table: SeasonalIndexTable
    store_count: int = 0
    category_summary: dict[str, int] = field(default_factory=dict)


class BaselineEngine:
    """基线预估引擎

    执行流程：
    1. 门店分类（6 分类）
    2. 计算季节指数（品牌×区域）
    3. 春节月判定
    4. 按分类调用对应预估器
    5. 汇总输出 baselines dict

    使用方式：
        engine = BaselineEngine()
        result = engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics_df,
            daily_sales_df=daily_sales_df,
            switch_status_df=switch_status_df,
            target_year=2026,
            target_month=5,
        )
        # result.baselines 可直接传给 TargetAllocator
    """

    def __init__(self, lunar_calendar: LunarCalendar | None = None):
        self._lunar = lunar_calendar or LunarCalendar()
        self._classifier = StoreClassifier(self._lunar)

    def run(
        self,
        stores_df: pd.DataFrame,
        monthly_metrics_df: pd.DataFrame,
        daily_sales_df: pd.DataFrame | None = None,
        switch_status_df: pd.DataFrame | None = None,
        target_year: int = 2026,
        target_month: int = 5,
        new_store_cutoff: str | None = None,
    ) -> BaselineEngineResult:
        """执行基线预估

        Args:
            stores_df: 门店主数据 DataFrame
            monthly_metrics_df: 月度指标 DataFrame
            daily_sales_df: 日销 DataFrame（可选，用于当月推全月）
            switch_status_df: 开关状态矩阵 DataFrame（可选）
            target_year: 预估年份
            target_month: 预估月份
            new_store_cutoff: 新店截止日期

        Returns:
            BaselineEngineResult
        """
        logger.info(f"基线预估引擎启动: 目标 {target_year}-{target_month:02d}")

        # Step 1: 门店分类
        classification = self._classifier.classify(
            stores_df, monthly_metrics_df,
            target_year, target_month,
            switch_status_df, new_store_cutoff,
        )
        logger.info(f"门店分类完成: {classification.summary}")

        # Step 2: 计算季节指数
        seasonal_calc = SeasonalIndexCalculator(self._lunar)
        seasonal_table = seasonal_calc.calculate(monthly_metrics_df, stores_df)
        logger.info(f"季节指数计算完成: {len(seasonal_table.indices)} 个品牌×区域组合")

        # Step 3: 判断是否春节月
        is_spring_festival = self._lunar.is_spring_festival_month(
            target_year, target_month
        )

        # Step 4: 初始化预估器
        large_est = LargeStoreEstimator(seasonal_table, self._lunar)
        small_est = SmallStoreEstimator(seasonal_table, self._lunar)
        new_est = NewStoreEstimator(seasonal_table)
        virtual_est = VirtualStoreEstimator(seasonal_table, self._lunar)
        temp_est = TempStoreEstimator(self._lunar)
        closing_est = ClosingStoreEstimator(seasonal_table, self._lunar)
        spring_est = SpringFestivalEstimator(self._lunar)

        # Step 5: 按分类调用预估器
        baselines = {}
        model_info = {}
        details = []

        for code, cls in classification.classifications.items():
            estimate = self._estimate_store(
                cls=cls,
                monthly_metrics_df=monthly_metrics_df,
                daily_sales_df=daily_sales_df,
                stores_df=stores_df,
                target_year=target_year,
                target_month=target_month,
                is_spring_festival=is_spring_festival,
                large_est=large_est,
                small_est=small_est,
                new_est=new_est,
                virtual_est=virtual_est,
                temp_est=temp_est,
                closing_est=closing_est,
                spring_est=spring_est,
            )

            baselines[code] = estimate.estimated_sales
            model_info[code] = {
                "category": cls.category.value,
                "mechanism": estimate.mechanism,
                "confidence": estimate.confidence,
                "seasonal_index": estimate.seasonal_index,
                "des_seasonal_sales": estimate.des_seasonal_sales,
                "brand": cls.brand,
                "region": cls.region,
                "avg_monthly_sales": cls.avg_monthly_sales,
                "valid_months": cls.valid_months,
                "reason": cls.reason,
                **estimate.extra,
            }
            details.append(estimate)

        # 汇总
        category_summary = {}
        for cat, count in classification.summary.items():
            category_summary[cat.value] = count

        result = BaselineEngineResult(
            baselines=baselines,
            model_info=model_info,
            classifications=classification,
            seasonal_table=seasonal_table,
            store_count=len(baselines),
            category_summary=category_summary,
        )

        logger.info(
            f"基线预估完成: {result.store_count} 家门店, "
            f"分类: {result.category_summary}"
        )

        return result

    def _estimate_store(
        self,
        cls,
        monthly_metrics_df: pd.DataFrame,
        daily_sales_df: pd.DataFrame | None,
        stores_df: pd.DataFrame,
        target_year: int,
        target_month: int,
        is_spring_festival: bool,
        large_est: LargeStoreEstimator,
        small_est: SmallStoreEstimator,
        new_est: NewStoreEstimator,
        virtual_est: VirtualStoreEstimator,
        temp_est: TempStoreEstimator,
        closing_est: ClosingStoreEstimator,
        spring_est: SpringFestivalEstimator,
    ) -> StoreEstimateDetail:
        """对单个门店进行预估"""

        code = cls.store_code
        brand = cls.brand
        region = cls.region

        # 春节月特殊处理（非临时特卖店、非关店）
        if is_spring_festival and cls.category not in (
            StoreCategory.TEMPORARY, StoreCategory.CLOSING,
        ):
            result = spring_est.estimate(
                code, monthly_metrics_df, target_year, target_month,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=result.estimated_sales,
                mechanism=result.method,
                confidence="medium",
                seasonal_index=1.0,
                des_seasonal_sales=result.estimated_sales,
                brand=brand,
                region=region,
                extra={"historical_months": result.historical_months},
            )

        # 按分类调用预估器
        if cls.category == StoreCategory.LARGE_MEDIUM:
            est = large_est.estimate(
                code, monthly_metrics_df, daily_sales_df,
                target_year, target_month, brand, region,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism=est.mechanism_used,
                confidence=est.confidence,
                seasonal_index=est.seasonal_index,
                des_seasonal_sales=est.des_seasonal_sales,
                brand=brand,
                region=region,
                extra={
                    "structural_ratio": est.structural_ratio,
                    "data_window_months": est.data_window_months,
                },
            )

        elif cls.category == StoreCategory.SMALL:
            est = small_est.estimate(
                code, monthly_metrics_df,
                target_year, target_month, brand, region,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism="deseasonalized_mean",
                confidence="medium",
                seasonal_index=est.seasonal_index,
                des_seasonal_sales=est.des_seasonal_sales,
                brand=brand,
                region=region,
                extra={"data_months": est.data_months},
            )

        elif cls.category == StoreCategory.NEW:
            est = new_est.estimate(
                code, stores_df, monthly_metrics_df,
                target_year, target_month, brand, region,
                cls.opening_date,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism="ramp_coefficient",
                confidence="medium",
                seasonal_index=1.0,
                des_seasonal_sales=est.estimated_sales,
                brand=brand,
                region=region,
                extra={
                    "reference_median": est.reference_median,
                    "ramp_coefficient": est.ramp_coefficient,
                    "opening_months": est.opening_months,
                },
            )

        elif cls.category == StoreCategory.VIRTUAL:
            est = virtual_est.estimate(
                code, monthly_metrics_df,
                target_year, target_month, brand, region,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism="deseasonalized_mean",
                confidence="medium",
                seasonal_index=est.seasonal_index,
                des_seasonal_sales=est.des_seasonal_sales,
                brand=brand,
                region=region,
                extra={"data_months": est.data_months},
            )

        elif cls.category == StoreCategory.TEMPORARY:
            est = temp_est.estimate(
                code, monthly_metrics_df,
                target_year, target_month,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism="raw_mean",
                confidence="medium",
                seasonal_index=1.0,
                des_seasonal_sales=est.estimated_sales,
                brand=brand,
                region=region,
                extra={
                    "data_months": est.data_months,
                    "participates_allocation": False,
                },
            )

        elif cls.category == StoreCategory.CLOSING:
            est = closing_est.estimate(
                code, monthly_metrics_df,
                target_year, target_month,
                cls.closing_date, brand, region,
            )
            return StoreEstimateDetail(
                store_code=code,
                category=cls.category,
                estimated_sales=est.estimated_sales,
                mechanism="closing_adjusted",
                confidence="medium",
                seasonal_index=1.0,
                des_seasonal_sales=est.base_estimate,
                brand=brand,
                region=region,
                extra={
                    "operating_days": est.operating_days,
                    "total_days": est.total_days,
                    "day_ratio": est.day_ratio,
                    "closing_date": est.closing_date,
                },
            )

        # 默认（不应到达）
        return StoreEstimateDetail(
            store_code=code,
            category=cls.category,
            estimated_sales=0.0,
            mechanism="unknown",
            confidence="low",
        )

"""基线预估 Agent

负责为每家门店建立利润基线预估。
使用业务规则引擎替代原有的 ARIMA/Prophet/指数平滑。
"""

from dataclasses import dataclass

import pandas as pd
from loguru import logger

from src.forecasting.rules.baseline_engine import BaselineEngine


@dataclass
class BaselineResult:
    """基线预估结果

    baselines: dict[str, float] — 核心输出，下游所有模块的输入
    model_info: dict[str, dict] — 模型信息，用于 API 返回
    """
    baselines: dict[str, float]             # {门店编码: 基线利润}
    model_info: dict[str, dict]             # {门店编码: 模型信息}
    accuracy: dict[str, dict] | None = None # {门店编码: 准确度指标}
    store_count: int = 0
    avg_mape: float = 0.0


class BaselineAgent:
    """基线预估 Agent

    使用业务规则引擎进行预估，支持两种调用方式：

    1. 新方式（推荐）：传入完整数据
        agent = BaselineAgent()
        result = agent.forecast(
            stores_df=stores_df,
            monthly_metrics=monthly_metrics,
            daily_sales=daily_sales,
            switch_status=switch_status,
            target_year=2026, target_month=5,
        )

    2. 旧方式（兼容）：仅传入月度指标
        agent = BaselineAgent()
        result = agent.forecast(monthly_metrics=monthly_metrics)
    """

    def __init__(self):
        self.engine = BaselineEngine()

    def forecast(
        self,
        monthly_metrics: pd.DataFrame,
        store_codes: list[str] | None = None,
        stores_df: pd.DataFrame | None = None,
        daily_sales: pd.DataFrame | None = None,
        switch_status: pd.DataFrame | None = None,
        target_year: int | None = None,
        target_month: int | None = None,
    ) -> BaselineResult:
        """为门店生成基线预估

        Args:
            monthly_metrics: 月度指标 DataFrame（需含 store_code, year_month, sales_amount）
            store_codes: 指定门店编码列表，None 则全部（仅旧模式使用）
            stores_df: 门店主数据 DataFrame（新模式必需）
            daily_sales: 日销 DataFrame（可选，用于当月推全月）
            switch_status: 开关状态矩阵 DataFrame（可选）
            target_year: 预估年份（可选，默认使用最新数据月份 + 1）
            target_month: 预估月份（可选）

        Returns:
            BaselineResult
        """
        # 新模式：有 stores_df 时使用完整引擎
        if stores_df is not None and not stores_df.empty:
            return self._forecast_with_engine(
                stores_df=stores_df,
                monthly_metrics=monthly_metrics,
                daily_sales=daily_sales,
                switch_status=switch_status,
                target_year=target_year,
                target_month=target_month,
            )

        # 旧模式：仅传入月度指标，自动推断参数
        return self._forecast_legacy(monthly_metrics, store_codes)

    def _forecast_with_engine(
        self,
        stores_df: pd.DataFrame,
        monthly_metrics: pd.DataFrame,
        daily_sales: pd.DataFrame | None,
        switch_status: pd.DataFrame | None,
        target_year: int | None,
        target_month: int | None,
    ) -> BaselineResult:
        """使用完整引擎预估"""
        # 推断目标年月
        if target_year is None or target_month is None:
            target_year, target_month = self._infer_target_month(monthly_metrics)

        engine_result = self.engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics,
            daily_sales_df=daily_sales,
            switch_status_df=switch_status,
            target_year=target_year,
            target_month=target_month,
        )

        result = BaselineResult(
            baselines=engine_result.baselines,
            model_info=engine_result.model_info,
            store_count=engine_result.store_count,
        )

        logger.info(
            f"基线预估完成（规则引擎）: {result.store_count} 家门店, "
            f"分类: {engine_result.category_summary}"
        )

        return result

    def _forecast_legacy(
        self,
        monthly_metrics: pd.DataFrame,
        store_codes: list[str] | None,
    ) -> BaselineResult:
        """旧模式预估（兼容接口）

        当没有门店主数据时，使用简单的均值法。
        """
        if store_codes is None:
            store_codes = monthly_metrics["store_code"].unique().tolist()

        baselines = {}
        model_info = {}

        for code in store_codes:
            store_data = monthly_metrics[monthly_metrics["store_code"] == code].copy()
            if store_data.empty:
                continue

            store_data = store_data.sort_values("year_month")

            if "sales_amount" not in store_data.columns:
                continue

            values = store_data["sales_amount"].tolist()
            if len(values) < 3:
                baselines[code] = sum(values) / len(values) if values else 0
                model_info[code] = {"model": "mean", "reason": "数据不足"}
                continue

            # 简单均值法（近3个月）
            recent = [v for v in values[-3:] if pd.notna(v) and v > 0]
            baseline = sum(recent) / len(recent) if recent else 0
            baselines[code] = baseline
            model_info[code] = {
                "model": "mean",
                "category": "unknown",
                "mechanism": "legacy_mean",
            }

        result = BaselineResult(
            baselines=baselines,
            model_info=model_info,
            store_count=len(baselines),
        )

        logger.info(
            f"基线预估完成（兼容模式）: {result.store_count} 家门店"
        )

        return result

    def _infer_target_month(self, monthly_metrics: pd.DataFrame) -> tuple[int, int]:
        """从月度指标中推断目标年月（最新数据月 + 1）"""
        if monthly_metrics.empty or "year_month" not in monthly_metrics.columns:
            from datetime import date
            today = date.today()
            return today.year, today.month

        ym_strs = monthly_metrics["year_month"].dropna().unique()
        if len(ym_strs) == 0:
            from datetime import date
            today = date.today()
            return today.year, today.month

        # 取最新月份
        latest = max(ym_strs)
        try:
            parts = str(latest).split("-")
            y, m = int(parts[0]), int(parts[1])
            # +1 个月
            m += 1
            if m > 12:
                m = 1
                y += 1
            return y, m
        except (ValueError, IndexError):
            from datetime import date
            today = date.today()
            return today.year, today.month

    def forecast_batch(
        self,
        monthly_metrics: pd.DataFrame,
        batch_size: int = 50,
    ) -> BaselineResult:
        """批量预估（分批处理，适合大量门店）"""
        store_codes = monthly_metrics["store_code"].unique().tolist()
        all_baselines = {}
        all_model_info = {}

        for i in range(0, len(store_codes), batch_size):
            batch_codes = store_codes[i:i + batch_size]
            batch_result = self._forecast_legacy(monthly_metrics, batch_codes)
            all_baselines.update(batch_result.baselines)
            all_model_info.update(batch_result.model_info)

        return BaselineResult(
            baselines=all_baselines,
            model_info=all_model_info,
            store_count=len(all_baselines),
        )

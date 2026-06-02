"""预测回测框架

12个月滚动预测验证，评估 BaselineEngine 的预测精度。

指标：
- WMAPE（加权平均绝对百分比误差）= Σ|pred-actual| / Σactual
- 汇总偏差 = (Σpred - Σactual) / Σactual
- 中位误差 = median(|pred-actual|/actual)

使用方式：
    backtester = PredictionBacktester()
    result = backtester.run(
        stores_df=stores,
        monthly_metrics=monthly_metrics,
        test_months=12,
    )
"""

from dataclasses import dataclass, field

import pandas as pd
from loguru import logger


@dataclass
class MonthBacktestResult:
    """单月回测结果"""
    target_month: str
    store_count: int
    total_predicted: float
    total_actual: float
    wmape: float                    # 加权平均绝对百分比误差
    aggregate_bias: float           # 汇总偏差
    median_ape: float               # 中位绝对百分比误差
    category_wmape: dict[str, float] = field(default_factory=dict)


@dataclass
class BacktestResult:
    """回测汇总"""
    test_months: int
    avg_wmape: float                # 平均 WMAPE
    avg_aggregate_bias: float       # 平均汇总偏差
    avg_median_ape: float           # 平均中位误差
    monthly_results: list[MonthBacktestResult] = field(default_factory=list)
    category_summary: dict[str, float] = field(default_factory=dict)  # {category: avg_wmape}


class PredictionBacktester:
    """预测回测器

    对最近 N 个月做滚动预测，与实际值比较，评估预测精度。
    """

    def run(
        self,
        stores_df: pd.DataFrame,
        monthly_metrics: pd.DataFrame,
        test_months: int = 12,
    ) -> BacktestResult:
        """执行滚动回测

        Args:
            stores_df: 门店主数据
            monthly_metrics: 月度指标（含 store_code, year_month, sales_amount）
            test_months: 回测月数

        Returns:
            BacktestResult
        """
        from src.forecasting.rules.baseline_engine import BaselineEngine

        engine = BaselineEngine()

        # 获取所有可用月份，排序
        all_months = sorted(monthly_metrics["year_month"].unique())
        if len(all_months) < test_months + 6:
            logger.warning(f"数据不足: {len(all_months)} 个月，需要至少 {test_months + 6}")
            test_months = max(1, len(all_months) - 6)

        # 取最后 test_months 个作为测试月
        test_month_list = all_months[-test_months:]
        monthly_results = []

        logger.info(f"预测回测开始: {test_months} 个月, 测试月={test_month_list[0]}~{test_month_list[-1]}")

        for target_ym in test_month_list:
            # 拆分 year 和 month
            parts = target_ym.split("-")
            target_year = int(parts[0])
            target_mon = int(parts[1])

            # 截取目标月之前的数据作为训练集
            train_data = monthly_metrics[monthly_metrics["year_month"] < target_ym].copy()

            if train_data.empty:
                continue

            # 只保留有训练数据的门店
            train_stores = train_data["store_code"].unique()
            train_stores_df = stores_df[stores_df["store_code"].isin(train_stores)]

            # 执行预测
            try:
                engine_result = engine.run(
                    stores_df=train_stores_df,
                    monthly_metrics_df=train_data,
                    target_year=target_year,
                    target_month=target_mon,
                )
                predictions = engine_result.baselines
            except Exception as e:
                logger.warning(f"预测失败 {target_ym}: {e}")
                continue

            # 获取实际值
            actual_data = monthly_metrics[monthly_metrics["year_month"] == target_ym]
            actuals = dict(zip(actual_data["store_code"], actual_data["sales_amount"]))

            # 计算指标
            month_result = self._compute_metrics(
                target_ym, predictions, actuals, train_stores_df,
            )
            monthly_results.append(month_result)

        if not monthly_results:
            return BacktestResult(
                test_months=0, avg_wmape=999, avg_aggregate_bias=999, avg_median_ape=999,
            )

        # 汇总
        avg_wmape = sum(r.wmape for r in monthly_results) / len(monthly_results)
        avg_bias = sum(r.aggregate_bias for r in monthly_results) / len(monthly_results)
        avg_median = sum(r.median_ape for r in monthly_results) / len(monthly_results)

        # 分类汇总
        category_wmapes = {}
        for r in monthly_results:
            for cat, wmape in r.category_wmape.items():
                category_wmapes.setdefault(cat, []).append(wmape)
        category_summary = {cat: sum(v)/len(v) for cat, v in category_wmapes.items()}

        result = BacktestResult(
            test_months=len(monthly_results),
            avg_wmape=round(avg_wmape, 4),
            avg_aggregate_bias=round(avg_bias, 4),
            avg_median_ape=round(avg_median, 4),
            monthly_results=monthly_results,
            category_summary=category_summary,
        )

        logger.info(
            f"预测回测完成: {result.test_months} 个月, "
            f"WMAPE={result.avg_wmape:.1%}, "
            f"汇总偏差={result.avg_aggregate_bias:.1%}, "
            f"中位误差={result.avg_median_ape:.1%}"
        )

        return result

    def _compute_metrics(
        self,
        target_ym: str,
        predictions: dict[str, float],
        actuals: dict[str, float],
        stores_df: pd.DataFrame,
    ) -> MonthBacktestResult:
        """计算单月指标"""
        # 构建门店分类映射
        cat_map = {}
        if "category" in stores_df.columns:
            cat_map = dict(zip(stores_df["store_code"], stores_df.get("category", pd.Series())))

        common_stores = set(predictions.keys()) & set(actuals.keys())
        if not common_stores:
            return MonthBacktestResult(
                target_month=target_ym, store_count=0,
                total_predicted=0, total_actual=0,
                wmape=999, aggregate_bias=999, median_ape=999,
            )

        total_abs_error = 0
        total_actual = 0
        total_predicted = 0
        apes = []
        cat_errors = {}  # {category: (abs_error, actual)}

        for code in common_stores:
            pred = predictions[code]
            act = actuals[code]
            if act <= 0:
                continue

            abs_error = abs(pred - act)
            ape = abs_error / act

            total_abs_error += abs_error
            total_actual += act
            total_predicted += pred
            apes.append(ape)

            # 分类统计
            cat = cat_map.get(code, "unknown")
            if cat not in cat_errors:
                cat_errors[cat] = [0, 0]
            cat_errors[cat][0] += abs_error
            cat_errors[cat][1] += act

        wmape = total_abs_error / total_actual if total_actual > 0 else 999
        aggregate_bias = (total_predicted - total_actual) / total_actual if total_actual > 0 else 999
        median_ape = sorted(apes)[len(apes)//2] if apes else 999

        # 分类 WMAPE
        category_wmape = {}
        for cat, (err, act) in cat_errors.items():
            category_wmape[cat] = err / act if act > 0 else 999

        return MonthBacktestResult(
            target_month=target_ym,
            store_count=len(common_stores),
            total_predicted=round(total_predicted, 0),
            total_actual=round(total_actual, 0),
            wmape=round(wmape, 4),
            aggregate_bias=round(aggregate_bias, 4),
            median_ape=round(median_ape, 4),
            category_wmape=category_wmape,
        )

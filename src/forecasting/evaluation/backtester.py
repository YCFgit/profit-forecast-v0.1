"""回测验证框架

.. deprecated::
    本模块依赖已废弃的 v1 统计模型（ModelSelector）。
    如需回测 v2 规则引擎，请直接使用 BaselineEngine.run() 对比历史数据。
"""

import warnings
from dataclasses import dataclass, field

import pandas as pd
from loguru import logger

from src.forecasting.evaluation.accuracy_metrics import AccuracyResult, evaluate

warnings.warn(
    "backtester 模块依赖已废弃的 v1 统计模型，将在未来版本移除。",
    DeprecationWarning,
    stacklevel=2,
)
from src.forecasting.models.model_selector import ModelSelector


@dataclass
class BacktestFold:
    """单次回测"""
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    actual: pd.Series
    predicted: pd.Series
    model_used: str
    accuracy: AccuracyResult


@dataclass
class BacktestResult:
    """回测汇总"""
    store_code: str
    n_folds: int
    folds: list[BacktestFold] = field(default_factory=list)
    avg_mape: float = 0.0
    avg_rmse: float = 0.0
    worst_fold_mape: float = 0.0
    best_fold_mape: float = 1.0
    model_usage: dict[str, int] = field(default_factory=dict)

    @property
    def is_reliable(self) -> bool:
        """模型是否可靠（MAPE < 20%）"""
        return self.avg_mape < 0.20


class Backtester:
    """滚动窗口回测器

    使用方式：
        backtester = Backtester(n_folds=3, test_months=3)
        result = backtester.run(store_code, monthly_series)
    """

    def __init__(
        self,
        n_folds: int = 3,
        test_months: int = 3,
        min_train_months: int = 12,
    ):
        """
        Args:
            n_folds: 回测折数
            test_months: 每折测试月数
            min_train_months: 最少训练月数
        """
        self.n_folds = n_folds
        self.test_months = test_months
        self.min_train_months = min_train_months

    def run(
        self,
        store_code: str,
        monthly_series: pd.Series,
    ) -> BacktestResult:
        """执行滚动窗口回测

        Args:
            store_code: 门店编码
            monthly_series: 月度序列

        Returns:
            BacktestResult
        """
        clean = monthly_series.dropna()
        total_months = len(clean)

        # 计算回测窗口
        folds_needed = self.n_folds * self.test_months + self.min_train_months
        if total_months < folds_needed:
            actual_folds = max(0, (total_months - self.min_train_months) // self.test_months)
            if actual_folds == 0:
                logger.warning(f"[{store_code}] 数据不足，无法回测")
                return BacktestResult(store_code=store_code, n_folds=0)
            logger.info(f"[{store_code}] 数据不足，调整回测折数为 {actual_folds}")
        else:
            actual_folds = self.n_folds

        result = BacktestResult(store_code=store_code, n_folds=actual_folds)

        for fold_idx in range(actual_folds):
            # 计算当前折的 train/test 范围
            test_end = total_months - fold_idx * self.test_months
            test_start = test_end - self.test_months
            train_end = test_start

            if train_end < self.min_train_months:
                break

            train = clean.iloc[:train_end]
            test = clean.iloc[test_start:test_end]

            if len(test) == 0:
                break

            # 选择模型并预测
            selector = ModelSelector(test_months=0, use_ensemble=False)
            selection = selector.select_and_predict(
                store_code=f"{store_code}_fold{fold_idx}",
                monthly_series=train,
                forecast_periods=len(test),
            )

            # 对齐预测值
            pred = selection.forecast.iloc[:len(test)]
            actual = test.iloc[:len(pred)]

            # 评估
            acc = evaluate(actual.values, pred.values)

            fold = BacktestFold(
                fold_index=fold_idx,
                train_start=str(train.index[0].date()),
                train_end=str(train.index[-1].date()),
                test_start=str(test.index[0].date()),
                test_end=str(test.index[-1].date()),
                actual=actual,
                predicted=pred,
                model_used=selection.best_model,
                accuracy=acc,
            )

            result.folds.append(fold)

            # 统计模型使用次数
            result.model_usage[selection.best_model] = (
                result.model_usage.get(selection.best_model, 0) + 1
            )

            logger.info(
                f"[{store_code}] 折{fold_idx}: "
                f"{fold.train_start}~{fold.train_end} → {fold.test_start}~{fold.test_end}, "
                f"模型={fold.model_used}, MAPE={acc.mape:.2%}"
            )

        # 汇总
        if result.folds:
            result.avg_mape = sum(f.accuracy.mape for f in result.folds) / len(result.folds)
            result.avg_rmse = sum(f.accuracy.rmse for f in result.folds) / len(result.folds)
            result.worst_fold_mape = max(f.accuracy.mape for f in result.folds)
            result.best_fold_mape = min(f.accuracy.mape for f in result.folds)

        logger.info(
            f"[{store_code}] 回测完成: {len(result.folds)}折, "
            f"平均MAPE={result.avg_mape:.2%}, "
            f"最优模型={max(result.model_usage, key=result.model_usage.get) if result.model_usage else 'N/A'}"
        )

        return result

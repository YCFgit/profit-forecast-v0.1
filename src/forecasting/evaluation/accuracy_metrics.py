"""预测精度评估指标

支持 MAPE、RMSE、MAE、R² 等常用指标。
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class AccuracyResult:
    """精度评估结果"""
    mape: float      # 平均绝对百分比误差
    rmse: float      # 均方根误差
    mae: float       # 平均绝对误差
    r2: float        # R² 决定系数
    bias: float      # 偏差（正=低估，负=高低估）
    sample_count: int

    def __repr__(self) -> str:
        return (
            f"AccuracyResult(MAPE={self.mape:.2%}, RMSE={self.rmse:,.0f}, "
            f"MAE={self.mae:,.0f}, R²={self.r2:.4f}, Bias={self.bias:.2%})"
        )

    @property
    def grade(self) -> str:
        """精度等级"""
        if self.mape < 0.10:
            return "A"  # 优秀
        elif self.mape < 0.20:
            return "B"  # 良好
        elif self.mape < 0.30:
            return "C"  # 一般
        else:
            return "D"  # 较差


def calc_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """平均绝对百分比误差 (MAPE)

    MAPE = mean(|actual - predicted| / |actual|)
    注意：actual 为 0 时跳过该样本
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])))


def calc_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """均方根误差 (RMSE)"""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def calc_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """平均绝对误差 (MAE)"""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    return float(np.mean(np.abs(actual - predicted)))


def calc_r2(actual: np.ndarray, predicted: np.ndarray) -> float:
    """R² 决定系数"""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - np.mean(actual)) ** 2)
    if ss_tot == 0:
        return 0.0
    return float(1 - ss_res / ss_tot)


def calc_bias(actual: np.ndarray, predicted: np.ndarray) -> float:
    """偏差率

    正值 = 模型低估实际值
    负值 = 模型高估实际值
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.sum() == 0:
        return 0.0
    return float((predicted.sum() - actual.sum()) / actual.sum())


def evaluate(actual: np.ndarray, predicted: np.ndarray) -> AccuracyResult:
    """综合评估"""
    return AccuracyResult(
        mape=calc_mape(actual, predicted),
        rmse=calc_rmse(actual, predicted),
        mae=calc_mae(actual, predicted),
        r2=calc_r2(actual, predicted),
        bias=calc_bias(actual, predicted),
        sample_count=len(actual),
    )


def evaluate_df(df: pd.DataFrame, actual_col: str, predicted_col: str) -> AccuracyResult:
    """从 DataFrame 评估"""
    return evaluate(df[actual_col].values, df[predicted_col].values)

"""集成模型 — 多模型加权平均

对多个模型的预测结果做加权平均。
权重可以基于回测精度自动计算。
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ModelWeight:
    """模型权重"""
    model_name: str
    weight: float
    mape: float  # 回测 MAPE


class EnsembleModel:
    """集成预测模型

    将多个基模型的预测结果做加权平均，降低单模型风险。

    使用方式：
        ensemble = EnsembleModel()
        predictions = {
            "ARIMA": arima_forecast,
            "Prophet": prophet_forecast,
            "ExpSmoothing": es_forecast,
        }
        result = ensemble.predict(predictions)
    """

    name = "Ensemble"

    def __init__(
        self,
        method: str = "inverse_mape",  # equal | inverse_mape | best
        min_models: int = 1,
    ):
        """
        Args:
            method: 权重计算方法
                - equal: 等权平均
                - inverse_mape: 按 MAPE 倒数加权（精度越高权重越大）
                - best: 直接选最优模型
            min_models: 最少参与集成的模型数
        """
        self.method = method
        self.min_models = min_models
        self.weights: list[ModelWeight] = []

    def predict(
        self,
        predictions: dict[str, pd.Series],
        mapes: dict[str, float] | None = None,
    ) -> pd.Series:
        """集成预测

        Args:
            predictions: {模型名: 预测序列}
            mapes: {模型名: 回测 MAPE}，inverse_mape 方法必须提供

        Returns:
            加权平均后的预测序列
        """
        if not predictions:
            raise ValueError("无预测结果")

        if len(predictions) < self.min_models:
            logger.warning(f"模型数不足 {self.min_models}，使用可用模型")

        # 计算权重
        weights = self._calc_weights(predictions.keys(), mapes)
        self.weights = weights

        # 加权平均
        result = None
        for model_name, pred in predictions.items():
            w = next((mw.weight for mw in weights if mw.model_name == model_name), 0)
            if w == 0:
                continue
            if result is None:
                result = pred * w
            else:
                result = result + pred * w

        if result is None:
            return pd.Series(dtype=float)

        result = result.clip(lower=0)

        logger.info(
            f"集成预测完成: {len(predictions)}个模型, "
            f"权重={', '.join(f'{mw.model_name}:{mw.weight:.2f}' for mw in weights)}"
        )

        return result

    def _calc_weights(
        self, model_names, mapes: dict[str, float] | None
    ) -> list[ModelWeight]:
        """计算模型权重"""
        weights = []

        if self.method == "equal":
            w = 1.0 / len(model_names)
            for name in model_names:
                mape = (mapes or {}).get(name, 0.0)
                weights.append(ModelWeight(name, w, mape))

        elif self.method == "inverse_mape":
            if not mapes:
                logger.warning("未提供 MAPE，回退到等权平均")
                return self._calc_weights(model_names, None)

            # 按 MAPE 倒数加权
            inverse_mapes = {}
            for name in model_names:
                mape = mapes.get(name, 0.3)  # 默认 30%
                inverse_mapes[name] = 1.0 / max(mape, 0.01)

            total = sum(inverse_mapes.values())
            for name in model_names:
                mape = mapes.get(name, 0.3)
                w = inverse_mapes[name] / total
                weights.append(ModelWeight(name, w, mape))

        elif self.method == "best":
            if not mapes:
                return self._calc_weights(model_names, None)
            best_name = min(mapes, key=mapes.get)
            for name in model_names:
                mape = mapes.get(name, 0.3)
                w = 1.0 if name == best_name else 0.0
                weights.append(ModelWeight(name, w, mape))

        else:
            raise ValueError(f"未知的权重方法: {self.method}")

        return weights

    def get_weights_summary(self) -> pd.DataFrame:
        """获取权重汇总"""
        if not self.weights:
            return pd.DataFrame()
        return pd.DataFrame([
            {"model": w.model_name, "weight": w.weight, "mape": w.mape}
            for w in self.weights
        ]).sort_values("weight", ascending=False)

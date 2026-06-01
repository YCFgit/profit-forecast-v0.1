"""折扣率回测器

WMAE（加权平均绝对误差）回测，用于选择最优预测方法。

WMAE = Σ(weight_i × |pred_i - actual_i|) / Σ(weight_i)
其中 weight_i = list_price_rev（吊牌价收入）

回测流程：
1. 按品牌×区域组织历史数据
2. 从第4个月开始回测（需至少3个前置月）
3. 对每个测试月，用所有方法预测，计算WMAE
4. 选WMAE最小的方法（覆盖率≥50%）
"""

from dataclasses import dataclass, field

from loguru import logger

from src.discount.discount_predictor import (
    DiscountPredictor,
    METHODS,
    SPRING_MONTHS,
)


@dataclass
class MethodBacktestResult:
    """单方法回测结果"""
    method: str
    wmae: float                    # 加权平均绝对误差
    mae: float                     # 平均绝对误差
    coverage: float                # 覆盖率 = 成功预测数 / 总预测数
    prediction_count: int          # 成功预测数
    total_count: int               # 总预测数
    errors: list[float] = field(default_factory=list)  # 各月误差


@dataclass
class BacktestResult:
    """回测汇总结果"""
    brand: str
    region: str
    best_method: str
    best_wmae: float
    method_results: dict[str, MethodBacktestResult] = field(default_factory=dict)
    test_months: list[int] = field(default_factory=list)


class DiscountBacktester:
    """折扣率回测器

    使用方式：
        backtester = DiscountBacktester()
        result = backtester.backtest(
            brand="NK",
            region="华东",
            history=[(202501, 72.5), (202502, 70.0), ...],
            weights=[(202501, 1000000), ...],  # (yyyymm, list_price_rev)
            national_history=[...],
        )
    """

    def backtest(
        self,
        brand: str,
        region: str,
        history: list[tuple[int, float]],
        weights: list[tuple[int, float]] | None = None,
        national_history: list[tuple[int, float]] | None = None,
        min_history_months: int = 4,
    ) -> BacktestResult:
        """执行回测

        Args:
            brand: 品牌
            region: 区域
            history: [(yyyymm, discount_rate), ...] 按时间升序
            weights: [(yyyymm, list_price_rev), ...] 用于WMAE权重
            national_history: 全国级历史
            min_history_months: 最少历史月数

        Returns:
            BacktestResult
        """
        predictor = DiscountPredictor()

        # 排序
        history = sorted(history, key=lambda x: x[0])
        weight_map = {ym: rev for ym, rev in (weights or [])}
        national_history = sorted(national_history or [], key=lambda x: x[0])

        # 过滤非春节月
        valid_history = [(ym, r) for ym, r in history if ym not in SPRING_MONTHS and r > 0]

        if len(valid_history) < min_history_months:
            logger.warning(f"回测数据不足: {brand} {region}, {len(valid_history)} < {min_history_months}")
            return BacktestResult(
                brand=brand, region=region,
                best_method="近期均值(3月)", best_wmae=999.0,
            )

        # 从第4个月开始回测
        test_months = [ym for ym, _ in valid_history[min_history_months - 1:]]

        # 各方法的误差累积
        method_errors = {m: [] for m in METHODS}
        method_weights = {m: [] for m in METHODS}

        for test_ym in test_months:
            # 实际值
            actual = None
            for ym, rate in valid_history:
                if ym == test_ym:
                    actual = rate
                    break
            if actual is None:
                continue

            # 截取测试月之前的数据作为历史
            test_idx = None
            for i, (ym, _) in enumerate(valid_history):
                if ym == test_ym:
                    test_idx = i
                    break
            if test_idx is None or test_idx < 1:
                continue

            sub_history = valid_history[:test_idx]
            sub_national = [(ym, r) for ym, r in national_history if ym < test_ym]

            # 用各方法预测
            target_month = f"{test_ym // 100}-{test_ym % 100:02d}"
            pred = predictor.predict(
                brand=brand,
                region=region,
                target_month=target_month,
                history=list(reversed(sub_history)),  # 降序
                national_history=list(reversed(sub_national)),
            )

            weight = weight_map.get(test_ym, 1.0)

            for method_name, predicted_val in pred.all_predictions.items():
                if predicted_val is not None:
                    error = abs(predicted_val - actual)
                    method_errors[method_name].append(error)
                    method_weights[method_name].append(weight)

        # 计算各方法的WMAE和覆盖率
        method_results = {}
        for method_name in METHODS:
            errors = method_errors[method_name]
            wts = method_weights[method_name]
            total = len(test_months)

            if not errors:
                method_results[method_name] = MethodBacktestResult(
                    method=method_name, wmae=999.0, mae=999.0,
                    coverage=0.0, prediction_count=0, total_count=total,
                )
                continue

            mae = sum(errors) / len(errors)
            wmae = (
                sum(w * e for w, e in zip(wts, errors)) / sum(wts)
                if sum(wts) > 0 else mae
            )
            coverage = len(errors) / total if total > 0 else 0

            method_results[method_name] = MethodBacktestResult(
                method=method_name,
                wmae=round(wmae, 4),
                mae=round(mae, 4),
                coverage=round(coverage, 4),
                prediction_count=len(errors),
                total_count=total,
                errors=errors,
            )

        # 选择最优方法
        best_method = self._select_best(method_results)

        result = BacktestResult(
            brand=brand,
            region=region,
            best_method=best_method,
            best_wmae=method_results[best_method].wmae if best_method in method_results else 999.0,
            method_results=method_results,
            test_months=test_months,
        )

        logger.info(
            f"折扣率回测完成: {brand} {region}, "
            f"最优={best_method}(WMAE={result.best_wmae:.2f}), "
            f"测试月={len(test_months)}个"
        )

        return result

    def _select_best(self, method_results: dict[str, MethodBacktestResult]) -> str:
        """选择最优方法

        规则：
        1. 覆盖率 ≥ 50% 才纳入候选（对"固定值"方法强制）
        2. 选 WMAE 最小的方法
        3. 兜底：近期均值(3月)
        """
        eligible = []
        for name, res in method_results.items():
            if name == "固定值" and res.coverage < 0.50:
                continue
            if res.prediction_count > 0:
                eligible.append((name, res.wmae))

        if not eligible:
            return "近期均值(3月)"

        eligible.sort(key=lambda x: x[1])
        return eligible[0][0]

    def batch_backtest(
        self,
        brand_region_data: dict[tuple[str, str], dict],
    ) -> dict[tuple[str, str], BacktestResult]:
        """批量回测多个品牌×区域

        Args:
            brand_region_data: {(brand, region): {
                "history": [(yyyymm, rate), ...],
                "weights": [(yyyymm, rev), ...],
                "national_history": [...],
            }}

        Returns:
            {(brand, region): BacktestResult}
        """
        results = {}
        for (brand, region), data in brand_region_data.items():
            results[(brand, region)] = self.backtest(
                brand=brand,
                region=region,
                history=data.get("history", []),
                weights=data.get("weights", []),
                national_history=data.get("national_history", []),
            )

        # 统计最优方法分布
        method_counts = {}
        for res in results.values():
            m = res.best_method
            method_counts[m] = method_counts.get(m, 0) + 1

        logger.info(f"批量回测完成: {len(results)} 个品牌×区域")
        logger.info(f"最优方法分布: {dict(sorted(method_counts.items(), key=lambda x: -x[1]))}")

        return results

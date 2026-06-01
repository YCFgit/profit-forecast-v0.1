"""折扣率预测器

11种预测方法 + WMAE回测选型，参考预算方法论 V3/V4。

方法列表：
1.  固定值 — 波动小的品牌用历史均值
2.  近期均值(3月) — 最近3个非春节月均值
3.  近期均值(2月) — 最近2个非春节月均值
4.  季节修正(3月) — 近期均值 × 季节因子
5.  季节修正(2月) — 同上，近2月
6.  全国近期均值 — 品牌全国级近3月均值
7.  全国季节修正 — 品牌全国级季节修正
8.  区域全国混合 — 0.5×区域 + 0.5×全国
9.  区域全国季节混合 — 0.5×区域季节修正 + 0.5×全国季节修正
10. 同比推算 — 去年同月 × (上月/去年上月)
11. 同比推算(均值锚定) — 近期均值 × (去年同月/去年相邻均值)

使用方式：
    predictor = DiscountPredictor()
    result = predictor.predict(
        brand="NK",
        region="华东",
        target_month="2026-06",
        history=[(202601, 72.5), (202512, 70.0), ...],
        national_history=[(202601, 73.0), ...],
    )
"""

from dataclasses import dataclass, field

from loguru import logger


# ── 春节月集合 ──────────────────────────────
SPRING_MONTHS = {202402, 202501, 202602}

# ── 季节因子截断范围 ──────────────────────────────
SEASONAL_CLIP_LOW = 0.70
SEASONAL_CLIP_HIGH = 1.30

# ── 固定值波动阈值（标准差 < 此值时用固定值） ──────────
FIXED_VOL_THRESHOLD = 1.0

# ── 折扣率使用截断 ──────────────────────────────
DISC_RATE_LOW = 0.30
DISC_RATE_HIGH = 1.00

# ── 全部方法名 ──────────────────────────────
METHODS = [
    "固定值",
    "近期均值(3月)",
    "近期均值(2月)",
    "季节修正(3月)",
    "季节修正(2月)",
    "全国近期均值",
    "全国季节修正",
    "区域全国混合",
    "区域全国季节混合",
    "同比推算",
    "同比推算(均值锚定)",
]


@dataclass
class DiscountPrediction:
    """折扣率预测结果"""
    brand: str
    region: str
    target_month: str
    predicted_rate: float          # 预测折扣率（已截断到[0.3, 1.0]）
    method: str                    # 使用的方法
    confidence: str = "medium"     # high / medium / low
    all_predictions: dict[str, float] = field(default_factory=dict)  # 各方法预测值
    best_method_wmae: float = 0.0  # 最优方法的WMAE


class DiscountPredictor:
    """折扣率预测器

    使用方式：
        predictor = DiscountPredictor()
        result = predictor.predict(
            brand="NK",
            region="华东",
            target_month="2026-06",
            history=[(202605, 72.5), (202604, 70.0), ...],  # (yyyymm, discount_rate)
            national_history=[(202605, 73.0), ...],
        )
    """

    def predict(
        self,
        brand: str,
        region: str,
        target_month: str,
        history: list[tuple[int, float]],
        national_history: list[tuple[int, float]] | None = None,
        best_method: str | None = None,
    ) -> DiscountPrediction:
        """预测折扣率

        Args:
            brand: 品牌
            region: 区域
            target_month: 目标月份 "YYYY-MM"
            history: [(yyyymm, discount_rate), ...] 区域级历史，按时间降序
            national_history: [(yyyymm, discount_rate), ...] 全国级历史
            best_method: 指定方法（跳过选型），否则自动选最优

        Returns:
            DiscountPrediction
        """
        target_ym = int(target_month.replace("-", ""))
        target_cal_month = int(target_month[5:7])

        # 排序确保降序
        history = sorted(history, key=lambda x: -x[0])
        national_history = sorted(national_history or [], key=lambda x: -x[0])

        # 各方法预测
        predictions = {}

        predictions["固定值"] = self._method_fixed(history)
        predictions["近期均值(3月)"] = self._method_recent_avg(history, n=3)
        predictions["近期均值(2月)"] = self._method_recent_avg(history, n=2)
        predictions["季节修正(3月)"] = self._method_seasonal_corrected(history, target_cal_month, n=3)
        predictions["季节修正(2月)"] = self._method_seasonal_corrected(history, target_cal_month, n=2)
        predictions["全国近期均值"] = self._method_recent_avg(national_history, n=3)
        predictions["全国季节修正"] = self._method_seasonal_corrected(national_history, target_cal_month, n=3)
        predictions["区域全国混合"] = self._method_blend(
            predictions.get("近期均值(3月)"),
            predictions.get("全国近期均值"),
        )
        predictions["区域全国季节混合"] = self._method_blend(
            predictions.get("季节修正(3月)"),
            predictions.get("全国季节修正"),
        )
        predictions["同比推算"] = self._method_yoy(history, target_ym)
        predictions["同比推算(均值锚定)"] = self._method_yoy_mean_anchored(history, target_ym, target_cal_month)

        # 过滤 None 值
        valid_predictions = {k: v for k, v in predictions.items() if v is not None}

        if not valid_predictions:
            # 全部失败，用默认值
            return DiscountPrediction(
                brand=brand,
                region=region,
                target_month=target_month,
                predicted_rate=DISC_RATE_LOW,
                method="默认兜底",
                confidence="low",
                all_predictions=predictions,
            )

        # 选择方法
        if best_method and best_method in valid_predictions:
            chosen_method = best_method
        else:
            chosen_method = self._select_best_method(valid_predictions, history)

        predicted = valid_predictions.get(chosen_method, list(valid_predictions.values())[0])
        predicted = max(DISC_RATE_LOW, min(DISC_RATE_HIGH, predicted))

        confidence = "high" if len(valid_predictions) >= 8 else "medium" if len(valid_predictions) >= 4 else "low"

        return DiscountPrediction(
            brand=brand,
            region=region,
            target_month=target_month,
            predicted_rate=round(predicted, 4),
            method=chosen_method,
            confidence=confidence,
            all_predictions={k: round(v, 4) if v else None for k, v in predictions.items()},
        )

    def _get_recent_non_spring(
        self,
        history: list[tuple[int, float]],
        n: int = 3,
    ) -> list[float]:
        """获取最近N个非春节月的折扣率"""
        result = []
        for ym, rate in history:
            if ym in SPRING_MONTHS:
                continue
            if rate > 0:
                result.append(rate)
            if len(result) >= n:
                break
        return result

    def _method_fixed(self, history: list[tuple[int, float]]) -> float | None:
        """方法1: 固定值 — 波动小用均值"""
        rates = [r for _, r in history if r > 0 and _ not in SPRING_MONTHS]
        if len(rates) < 3:
            return None
        import statistics
        std = statistics.stdev(rates)
        if std < FIXED_VOL_THRESHOLD:
            return statistics.mean(rates)
        return None

    def _method_recent_avg(
        self,
        history: list[tuple[int, float]],
        n: int = 3,
    ) -> float | None:
        """方法2/3/6: 近期均值"""
        recent = self._get_recent_non_spring(history, n)
        if not recent:
            return None
        return sum(recent) / len(recent)

    def _method_seasonal_corrected(
        self,
        history: list[tuple[int, float]],
        target_cal_month: int,
        n: int = 3,
    ) -> float | None:
        """方法4/5/7: 季节修正

        公式: 近期均值 × 季节因子
        季节因子 = 去年同月 / 去年前后相邻3月均值，截断到[0.7, 1.3]
        """
        recent_avg = self._method_recent_avg(history, n)
        if recent_avg is None:
            return None

        # 找去年同月
        ly_month = None
        ly_neighbors = []
        for ym, rate in history:
            if rate <= 0 or ym in SPRING_MONTHS:
                continue
            cal_m = ym % 100
            if cal_m == target_cal_month and ly_month is None:
                ly_month = rate
            # 去年前后相邻月（用于计算季节因子分母）
            if abs(cal_m - target_cal_month) <= 1 and ly_month is not None:
                if rate != ly_month:
                    ly_neighbors.append(rate)

        if ly_month is None:
            return recent_avg  # 无去年同月，退化为近期均值

        # 去年前后3月均值
        ly_all = [(ym, r) for ym, r in history if r > 0 and ym not in SPRING_MONTHS]
        # 找去年同月附近3个月
        ly_target_ym = None
        for ym, _ in ly_all:
            cal_m = ym % 100
            if cal_m == target_cal_month:
                ly_target_ym = ym
                break

        if ly_target_ym is None:
            return recent_avg

        # 去年同月的前后各1个月
        neighbor_rates = []
        for ym, rate in ly_all:
            diff = abs(ym - ly_target_ym)
            if diff <= 1 and diff > 0:  # 前后1个月
                neighbor_rates.append(rate)
            elif diff == 0:
                continue

        if not neighbor_rates:
            return recent_avg

        neighbor_avg = sum(neighbor_rates) / len(neighbor_rates)
        if neighbor_avg <= 0:
            return recent_avg

        seasonal_factor = ly_month / neighbor_avg
        seasonal_factor = max(SEASONAL_CLIP_LOW, min(SEASONAL_CLIP_HIGH, seasonal_factor))

        return recent_avg * seasonal_factor

    def _method_blend(
        self,
        regional: float | None,
        national: float | None,
    ) -> float | None:
        """方法8/9: 区域全国混合 (50/50)"""
        if regional is not None and national is not None:
            return 0.5 * regional + 0.5 * national
        return regional or national

    def _method_yoy(
        self,
        history: list[tuple[int, float]],
        target_ym: int,
    ) -> float | None:
        """方法10: 同比推算

        公式: disc_pred_T = disc_{T-12} × (disc_{T-1} / disc_{T-13})
        """
        # 构建 ym -> rate 映射
        rate_map = {ym: rate for ym, rate in history if rate > 0 and ym not in SPRING_MONTHS}

        # T-12 = 去年同月
        target_year = target_ym // 100
        target_month = target_ym % 100
        ly_ym = (target_year - 1) * 100 + target_month  # 去年同月

        # T-1 = 上月
        if target_month == 1:
            lm_ym = (target_year - 1) * 100 + 12
        else:
            lm_ym = target_year * 100 + (target_month - 1)

        # T-13 = 去年上月
        if target_month == 1:
            ly_lm_ym = (target_year - 2) * 100 + 12
        else:
            ly_lm_ym = (target_year - 1) * 100 + (target_month - 1)

        disc_ly = rate_map.get(ly_ym)
        disc_lm = rate_map.get(lm_ym)
        disc_ly_lm = rate_map.get(ly_lm_ym)

        if disc_ly is None:
            return None

        if disc_lm is not None and disc_ly_lm is not None and disc_ly_lm > 0:
            yoy_rate = disc_lm / disc_ly_lm
            return disc_ly * yoy_rate

        # 兜底：只有去年同月
        return disc_ly

    def _method_yoy_mean_anchored(
        self,
        history: list[tuple[int, float]],
        target_ym: int,
        target_cal_month: int,
    ) -> float | None:
        """方法11: 同比推算(均值锚定)

        公式: disc_pred_T = 近期均值 × (disc_{T-12} / disc_{T-13~T-11均值})
        """
        recent_avg = self._method_recent_avg(history, n=3)
        if recent_avg is None:
            return None

        rate_map = {ym: rate for ym, rate in history if rate > 0 and ym not in SPRING_MONTHS}

        target_year = target_ym // 100
        ly_ym = (target_year - 1) * 100 + target_cal_month

        disc_ly = rate_map.get(ly_ym)
        if disc_ly is None:
            return recent_avg

        # 去年相邻3月均值
        neighbor_rates = []
        for ym, rate in history:
            if rate <= 0 or ym in SPRING_MONTHS:
                continue
            cal_m = ym % 100
            y = ym // 100
            if y == target_year - 1 and abs(cal_m - target_cal_month) <= 1:
                neighbor_rates.append(rate)

        if not neighbor_rates:
            return recent_avg

        neighbor_avg = sum(neighbor_rates) / len(neighbor_rates)
        if neighbor_avg <= 0:
            return recent_avg

        seasonal_ratio = disc_ly / neighbor_avg
        seasonal_ratio = max(SEASONAL_CLIP_LOW, min(SEASONAL_CLIP_HIGH, seasonal_ratio))

        return recent_avg * seasonal_ratio

    def _select_best_method(
        self,
        predictions: dict[str, float],
        history: list[tuple[int, float]],
    ) -> str:
        """选择最优方法（简化版：基于数据可用性）

        完整版应使用WMAE回测（见 backtester.py），
        这里用启发式规则：优先季节修正 > 同比推算 > 近期均值
        """
        priority = [
            "季节修正(3月)",
            "季节修正(2月)",
            "同比推算",
            "同比推算(均值锚定)",
            "区域全国季节混合",
            "区域全国混合",
            "全国季节修正",
            "近期均值(3月)",
            "近期均值(2月)",
            "全国近期均值",
            "固定值",
        ]
        for method in priority:
            if method in predictions:
                return method
        return list(predictions.keys())[0]

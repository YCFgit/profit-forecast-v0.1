"""基线预估 Agent

职责：从销售数据推算基线收入和折扣预测。
使用 BaselineEngine 的完整预估流程（门店分类 + 季节指数 + 加权近月 + 结构检测）。
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from loguru import logger

from src.forecasting.rules.baseline_engine import BaselineEngine


@dataclass
class BaselineResult:
    """基线预估结果"""
    store_count: int
    avg_mape: float
    baselines: dict[str, float]
    model_info: dict[str, dict] = field(default_factory=dict)


@dataclass
class PredictionResult:
    """目标月份预测结果"""
    target_month: str
    store_count: int
    total_predicted: float
    baselines: dict[str, float]
    confidence_intervals: dict[str, dict]  # {store_code: {low, mid, high}}
    region_summary: dict[str, dict]  # {region: {predicted, store_count, avg_per_store}}
    brand_summary: dict[str, dict]  # {brand: {predicted, store_count}}
    category_summary: dict[str, int]
    model_info: dict[str, dict] = field(default_factory=dict)


class BaselineAgent:
    """基线预估 Agent

    forecast(): 用 BaselineEngine 做完整预估（加权近月+结构检测+季节指数）
    predict():  用 BaselineEngine + 置信区间 + 区域/品牌汇总
    estimate(): 从日销宽表估算（同比融合）
    """

    def __init__(self):
        self.name = "BaselineAgent"
        self.engine = BaselineEngine()

    def _get_default_target(self) -> tuple[int, int]:
        """获取默认目标月（下个月）"""
        today = date.today()
        y, m = today.year, today.month
        m += 1
        if m > 12:
            m = 1
            y += 1
        return y, m

    def forecast(
        self,
        monthly_metrics: pd.DataFrame,
        stores_df: pd.DataFrame = None,
        daily_sales: pd.DataFrame = None,
        switch_status: pd.DataFrame = None,
    ) -> BaselineResult:
        """从月度指标推算基线收入（API 路由入口）

        使用 BaselineEngine 的完整预估流程：
        - 门店6分类（大中/小店/新店/虚拟/临特/关店）
        - 品牌×区域季节指数（阻尼50%）
        - 大中店加权近月预估（weights=[0.35,0.25,0.18,0.12,0.07,0.03]）
        - 结构性变化检测（近3月/近12月 < 0.70 或 > 1.30 触发短窗口）
        - 新店爬坡系数、关店按天折算

        Args:
            monthly_metrics: 月度指标 DataFrame（含 store_code, sales_amount, year_month）
            stores_df: 门店 DataFrame（含 store_code, brand, region, opening_date 等）
            daily_sales: 日销 DataFrame（可选，用于当月推全月）
            switch_status: 开关状态 DataFrame（可选）

        Returns:
            BaselineResult
        """
        logger.info(
            f"[{self.name}] 开始基线预估: "
            f"{monthly_metrics['store_code'].nunique()} 家门店"
        )

        # 确定目标月（下个月）
        target_year, target_month = self._get_default_target()

        # 如果没有门店数据，降级为简单均值
        if stores_df is None or stores_df.empty:
            logger.warning(f"[{self.name}] 无门店数据，降级为简单均值")
            return self._fallback_forecast(monthly_metrics)

        # 只保留有月度数据的门店
        stores_with_metrics = monthly_metrics["store_code"].unique()
        stores_df = stores_df[stores_df["store_code"].isin(stores_with_metrics)]

        # 用 BaselineEngine 执行完整预估
        engine_result = self.engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics,
            daily_sales_df=daily_sales,
            switch_status_df=switch_status,
            target_year=target_year,
            target_month=target_month,
        )

        baselines = engine_result.baselines
        model_info = engine_result.model_info

        # 计算平均 MAPE（基于门店分类的典型误差水平）
        category_mape = {
            "large_medium": 0.296,
            "small": 0.163,
            "new": 1.534,
            "virtual": 0.386,
            "temporary": 0.554,
            "closing": 0.30,
        }
        mape_values = []
        for code, info in model_info.items():
            cat = info.get("category", "small")
            mape_values.append(category_mape.get(cat, 0.30))
        avg_mape = sum(mape_values) / len(mape_values) if mape_values else 0.30

        logger.info(
            f"[{self.name}] 基线预估完成: {len(baselines)} 家门店, "
            f"目标月={target_year}-{target_month:02d}, "
            f"分类={engine_result.category_summary}"
        )
        return BaselineResult(
            store_count=len(baselines),
            avg_mape=avg_mape,
            baselines=baselines,
            model_info=model_info,
        )

    def _fallback_forecast(self, monthly_metrics: pd.DataFrame) -> BaselineResult:
        """降级预估（无门店数据时使用简单均值）"""
        baselines = {}
        model_info = {}
        for store_code in monthly_metrics["store_code"].unique():
            store_data = monthly_metrics[monthly_metrics["store_code"] == store_code]
            recent = store_data.sort_values("year_month").tail(3)
            baseline = recent["sales_amount"].mean() if not recent.empty else 0.0
            baselines[store_code] = round(baseline, 2)
            model_info[store_code] = {
                "category": "unknown",
                "mechanism": "fallback_moving_average",
                "confidence": "low",
            }
        return BaselineResult(
            store_count=len(baselines),
            avg_mape=0.30,
            baselines=baselines,
            model_info=model_info,
        )

    def predict(
        self,
        target_month: str,
        stores_df: pd.DataFrame,
        monthly_metrics: pd.DataFrame,
        daily_sales: pd.DataFrame | None = None,
        switch_status: pd.DataFrame | None = None,
    ) -> PredictionResult:
        """预测指定月份的销售额

        使用 BaselineEngine 的完整预测流程（门店分类 + 季节指数 + 6种预估器），
        并基于历史预测误差计算置信区间。

        Args:
            target_month: 目标月份，格式 "YYYY-MM"
            stores_df: 门店主数据
            monthly_metrics: 月度指标
            daily_sales: 日销数据（可选）
            switch_status: 开关状态（可选）

        Returns:
            PredictionResult
        """
        target_year = int(target_month[:4])
        target_mon = int(target_month[5:7])

        logger.info(
            f"[{self.name}] 预测 {target_month}: "
            f"{monthly_metrics['store_code'].nunique()} 家门店"
        )

        # 1. 用 BaselineEngine 执行完整预测
        engine_result = self.engine.run(
            stores_df=stores_df,
            monthly_metrics_df=monthly_metrics,
            daily_sales_df=daily_sales,
            switch_status_df=switch_status,
            target_year=target_year,
            target_month=target_mon,
        )

        baselines = engine_result.baselines

        # 2. 计算置信区间（基于历史预测误差）
        ci = self._compute_confidence_intervals(
            baselines, monthly_metrics, stores_df,
        )

        # 3. 区域汇总
        region_map = stores_df.set_index("store_code")["region"].to_dict()
        region_summary = {}
        for code, pred_sales in baselines.items():
            region = region_map.get(code, "未知")
            if region not in region_summary:
                region_summary[region] = {"predicted": 0, "store_count": 0}
            region_summary[region]["predicted"] += pred_sales
            region_summary[region]["store_count"] += 1
        for r in region_summary.values():
            r["avg_per_store"] = round(r["predicted"] / r["store_count"], 0) if r["store_count"] > 0 else 0
        region_summary = dict(sorted(region_summary.items(), key=lambda x: -x[1]["predicted"]))

        # 4. 品牌汇总
        brand_map = stores_df.set_index("store_code")["brand"].to_dict() if "brand" in stores_df.columns else {}
        brand_summary = {}
        for code, pred_sales in baselines.items():
            brand = brand_map.get(code, "未知")
            if brand not in brand_summary:
                brand_summary[brand] = {"predicted": 0, "store_count": 0}
            brand_summary[brand]["predicted"] += pred_sales
            brand_summary[brand]["store_count"] += 1
        brand_summary = dict(sorted(brand_summary.items(), key=lambda x: -x[1]["predicted"]))

        total_predicted = sum(baselines.values())

        logger.info(
            f"[{self.name}] {target_month} 预测完成: "
            f"总额 ¥{total_predicted:,.0f}, {len(baselines)} 家门店"
        )

        return PredictionResult(
            target_month=target_month,
            store_count=len(baselines),
            total_predicted=round(total_predicted, 0),
            baselines=baselines,
            confidence_intervals=ci,
            region_summary=region_summary,
            brand_summary=brand_summary,
            category_summary=engine_result.category_summary,
            model_info=engine_result.model_info,
        )

    def _compute_confidence_intervals(
        self,
        baselines: dict[str, float],
        monthly_metrics: pd.DataFrame,
        stores_df: pd.DataFrame,
    ) -> dict[str, dict]:
        """计算置信区间

        基于每家门店的历史月度销售额波动率（变异系数 CV），
        计算乐观(+1σ)、中性(预测值)、悲观(-1σ)三个场景。
        """
        ci = {}
        for code, pred in baselines.items():
            store_data = monthly_metrics[monthly_metrics["store_code"] == code]
            if len(store_data) < 3 or pred <= 0:
                ci[code] = {
                    "low": round(pred * 0.8, 0),
                    "mid": round(pred, 0),
                    "high": round(pred * 1.2, 0),
                    "cv": 0.2,
                }
                continue

            # 计算变异系数
            sales = store_data["sales_amount"]
            cv = sales.std() / sales.mean() if sales.mean() > 0 else 0.2
            cv = min(cv, 0.5)  # 上限 50%

            # 置信区间：±1σ 对应约 68% 置信度
            low = pred * (1 - cv)
            high = pred * (1 + cv)

            ci[code] = {
                "low": round(low, 0),
                "mid": round(pred, 0),
                "high": round(high, 0),
                "cv": round(cv, 4),
            }

        return ci

    def estimate(
        self,
        sales_df: pd.DataFrame,
        date_range: tuple = None,
    ) -> dict:
        """估算基线收入

        优化策略：
        - 如有同比数据(ly_sales)，用 60%近期 + 40%同比 加权，减少季节波动
        - 如有预算数据(budget_sales)，作为参考信号
        - 否则退化为近期30天均值

        Args:
            sales_df: 统一销售宽表
            date_range: 预测目标日期范围

        Returns:
            {store_baselines: {store_no: baseline_revenue}, discount_forecasts: {...}}
        """
        logger.info(f"[{self.name}] 开始基线预估: {sales_df['store_no'].nunique()} 家门店")

        # 1. 基线收入估算（向量化：每店取最近30天的日均收入 × 30）
        sorted_df = sales_df.sort_values("base_date")
        recent_30 = sorted_df.groupby("store_no").tail(30)
        daily_avg = recent_30.groupby("store_no")["revenue"].mean()

        # 2. 如有同比数据，用加权融合减少季节波动
        if "ly_sales" in sales_df.columns and sales_df["ly_sales"].notna().any():
            ly_daily_avg = recent_30.groupby("store_no")["ly_sales"].mean()
            # 合并：近期60% + 同比40%（同比为0的不参与）
            merged = pd.DataFrame({"recent": daily_avg, "ly": ly_daily_avg}).fillna(0)
            has_ly = merged["ly"] > 0
            blended = merged["recent"].copy()
            blended[has_ly] = merged.loc[has_ly, "recent"] * 0.6 + merged.loc[has_ly, "ly"] * 0.4
            store_baselines = (blended * 30).round(2).to_dict()
            ly_count = has_ly.sum()
            logger.info(f"[{self.name}] 同比融合: {ly_count}/{len(merged)} 家门店有同比数据")
        else:
            store_baselines = (daily_avg * 30).round(2).to_dict()

        # 3. 折扣预测（向量化）
        discount_forecasts = {}
        try:
            brand_discount = sales_df.groupby("brand")["avg_discount"].mean()
            for brand, avg_discount in brand_discount.items():
                discount_forecasts[brand] = {
                    "current_avg_discount": round(avg_discount, 4),
                    "forecast_next_month": round(avg_discount * 0.98, 4),
                }
        except Exception as e:
            logger.warning(f"折扣预测失败: {e}")

        logger.info(f"[{self.name}] 基线预估完成: {len(store_baselines)} 家门店")
        return {
            "store_baselines": store_baselines,
            "discount_forecasts": discount_forecasts,
        }

    def predict_yoy(
        self,
        monthly_metrics: pd.DataFrame,
        stores_df: pd.DataFrame | None = None,
        cost_structures: dict[str, dict] | None = None,
    ) -> dict:
        """同比预测本月和下月利润

        使用三种信号融合预测：
        - 上月实际 (LM) — 短期趋势，权重 0.40
        - 去年同月 (LY) — 季节基准，权重 0.35
        - 去年下月 (LY_NM) — 季节趋势，权重 0.25

        公式：
            预测本月 = 0.40 × LM + 0.35 × LY + 0.25 × LY_NM
            预测下月 = 0.40 × 本月预测 + 0.35 × LY_NM + 0.25 × LY_NM2(去年再下月)

        Args:
            monthly_metrics: 月度指标 DataFrame（含 store_code, year_month, sales_amount）
            stores_df: 门店主数据（可选，用于获取品牌/区域）
            cost_structures: 成本结构（可选，用于利润推算）

        Returns:
            {
                "current_month": {"month": "2026-06", "baselines": {...}, "total": float},
                "next_month": {"month": "2026-07", "baselines": {...}, "total": float},
                "store_details": [{store_code, lm, ly, ly_nm, pred_current, pred_next}, ...]
            }
        """
        from datetime import date
        import math

        today = date.today()
        cur_year, cur_month = today.year, today.month
        cur_ym = f"{cur_year}-{cur_month:02d}"

        # 下月
        nm_year, nm_month = cur_year, cur_month + 1
        if nm_month > 12:
            nm_month = 1
            nm_year += 1
        nm_ym = f"{nm_year}-{nm_month:02d}"

        # 去年同月
        ly_ym = f"{cur_year - 1}-{cur_month:02d}"

        # 去年下月
        ly_nm_month = cur_month + 1
        ly_nm_year = cur_year - 1
        if ly_nm_month > 12:
            ly_nm_month = 1
            ly_nm_year += 1
        ly_nm_ym = f"{ly_nm_year}-{ly_nm_month:02d}"

        # 去年再下月（用于预测下月）
        ly_nm2_month = cur_month + 2
        ly_nm2_year = cur_year - 1
        if ly_nm2_month > 12:
            ly_nm2_month = 1
            ly_nm2_year += 1
        ly_nm2_ym = f"{ly_nm2_year}-{ly_nm2_month:02d}"

        # 上月
        lm_month = cur_month - 1
        lm_year = cur_year
        if lm_month < 1:
            lm_month = 12
            lm_year -= 1
        lm_ym = f"{lm_year}-{lm_month:02d}"

        logger.info(
            f"[{self.name}] 同比预测: 本月={cur_ym}, 下月={nm_ym}, "
            f"上月={lm_ym}, 去年同月={ly_ym}, 去年下月={ly_nm_ym}"
        )

        # 构建 (store_code, year_month) -> sales_amount 映射
        sales_map = {}
        for _, row in monthly_metrics.iterrows():
            sales_map[(row["store_code"], row["year_month"])] = row["sales_amount"]

        all_stores = monthly_metrics["store_code"].unique()

        current_baselines = {}
        next_baselines = {}
        store_details = []

        for code in all_stores:
            lm_val = sales_map.get((code, lm_ym), 0)
            ly_val = sales_map.get((code, ly_ym), 0)
            ly_nm_val = sales_map.get((code, ly_nm_ym), 0)
            ly_nm2_val = sales_map.get((code, ly_nm2_ym), 0)

            # 跳过全部为 0 的门店
            if lm_val == 0 and ly_val == 0 and ly_nm_val == 0:
                continue

            # NaN 处理
            for v in [lm_val, ly_val, ly_nm_val, ly_nm2_val]:
                if isinstance(v, float) and math.isnan(v):
                    v = 0

            # 信号数量决定权重分配
            signals_current = []
            if lm_val > 0:
                signals_current.append(("lm", lm_val, 0.40))
            if ly_val > 0:
                signals_current.append(("ly", ly_val, 0.35))
            if ly_nm_val > 0:
                signals_current.append(("ly_nm", ly_nm_val, 0.25))

            if not signals_current:
                continue

            # 归一化权重
            total_w = sum(w for _, _, w in signals_current)
            pred_current = sum(v * w / total_w for _, v, w in signals_current)

            # 预测下月
            signals_next = []
            if pred_current > 0:
                signals_next.append(("pred_current", pred_current, 0.40))
            if ly_nm_val > 0:
                signals_next.append(("ly_nm", ly_nm_val, 0.35))
            if ly_nm2_val > 0:
                signals_next.append(("ly_nm2", ly_nm2_val, 0.25))

            if signals_next:
                total_w_next = sum(w for _, _, w in signals_next)
                pred_next = sum(v * w / total_w_next for _, v, w in signals_next)
            else:
                pred_next = pred_current

            current_baselines[code] = round(pred_current, 0)
            next_baselines[code] = round(pred_next, 0)

            store_details.append({
                "store_code": code,
                "last_month": round(lm_val, 0),
                "last_year_same": round(ly_val, 0),
                "last_year_next": round(ly_nm_val, 0),
                "pred_current": round(pred_current, 0),
                "pred_next": round(pred_next, 0),
            })

        # 排序
        store_details.sort(key=lambda x: -x["pred_current"])

        result = {
            "current_month": {
                "month": cur_ym,
                "baselines": current_baselines,
                "total": round(sum(current_baselines.values()), 0),
                "store_count": len(current_baselines),
            },
            "next_month": {
                "month": nm_ym,
                "baselines": next_baselines,
                "total": round(sum(next_baselines.values()), 0),
                "store_count": len(next_baselines),
            },
            "store_details": store_details,
        }

        logger.info(
            f"[{self.name}] 同比预测完成: "
            f"本月 {cur_ym}=¥{result['current_month']['total']:,.0f} ({result['current_month']['store_count']}家), "
            f"下月 {nm_ym}=¥{result['next_month']['total']:,.0f} ({result['next_month']['store_count']}家)"
        )

        return result

    def _estimate_store_baseline(self, store_no: str, store_data: pd.DataFrame) -> float:
        """估算单店基线收入"""
        # 简单取最近 N 天的平均值 × 30
        recent = store_data.sort_values("base_date").tail(30)
        if recent.empty:
            return 0.0
        daily_avg = recent["revenue"].mean()
        return round(daily_avg * 30, 2)

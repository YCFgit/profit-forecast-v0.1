"""预测验证脚本 — 等价于 BaselineEngine 全流程的 SQL 实现"""
import pymysql
from collections import defaultdict, Counter
from datetime import datetime
import calendar

TARGET_YEAR = 2026
TARGET_MONTH = 6
TARGET_YM = f"{TARGET_YEAR}-{TARGET_MONTH:02d}"

# 春节月 (2024:2月, 2025:1月, 2026:2月)
SPRING_FESTIVAL = {(2024, 2), (2025, 1), (2026, 2)}

def is_spring(cy, cm):
    return (cy, cm) in SPRING_FESTIVAL

# 春节排除条件 (SQL 片段)
SF_EXCLUDE = """NOT (
    (CAST(SUBSTR(m.`year_month`, 1, 4) AS UNSIGNED) = 2024 AND CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) = 2)
    OR (CAST(SUBSTR(m.`year_month`, 1, 4) AS UNSIGNED) = 2025 AND CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) = 1)
    OR (CAST(SUBSTR(m.`year_month`, 1, 4) AS UNSIGNED) = 2026 AND CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) = 2)
)"""

conn = pymysql.connect(
    host='localhost', port=3307, user='root',
    password='profit123', database='profit_forecast', charset='utf8mb4'
)
cursor = conn.cursor()

# ─────────────────────────────────────
# Step 1: 季节指数 (品牌×区域×月)
# ─────────────────────────────────────
print("=" * 60)
print("Step 1: 季节指数")
sql = f"""
SELECT s.brand, s.region,
    CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) AS cm,
    AVG(m.sales_amount) AS ma
FROM store_monthly_metrics m
JOIN stores s ON m.store_code = s.store_code
WHERE m.sales_amount > 0 AND {SF_EXCLUDE}
  AND m.`year_month` < '{TARGET_YM}'
GROUP BY s.brand, s.region, CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED)
"""
cursor.execute(sql)
rows = cursor.fetchall()

br_months = defaultdict(lambda: defaultdict(float))
for brand, region, cm, ma in rows:
    br_months[(brand, region)][cm] = float(ma)

overall = {k: sum(v.values()) / len(v) for k, v in br_months.items() if v}
seasonal = {}
for key, months in br_months.items():
    ov = overall.get(key, 0)
    if ov <= 0:
        continue
    for m, avg in months.items():
        raw = avg / ov
        seasonal[(key[0], key[1], m)] = 1.0 + (raw - 1.0) * 0.50

print(f"  季节指数: {len(seasonal)} 条")

# ─────────────────────────────────────
# Step 2: 门店分类
# ─────────────────────────────────────
print("Step 2: 门店分类")
sql = f"""
SELECT s.store_code, s.brand, s.region, s.opening_date, s.closing_date,
    SUM(CASE WHEN {SF_EXCLUDE} AND m.`year_month` < '{TARGET_YM}' AND m.sales_amount > 0 THEN 1 ELSE 0 END) AS valid_months,
    AVG(CASE WHEN {SF_EXCLUDE} AND m.`year_month` < '{TARGET_YM}' AND m.sales_amount > 0 THEN m.sales_amount ELSE NULL END) AS avg_sales
FROM stores s
LEFT JOIN store_monthly_metrics m ON s.store_code = m.store_code
GROUP BY s.store_code, s.brand, s.region, s.opening_date, s.closing_date
"""
cursor.execute(sql)
cats = {}
for code, brand, region, od, cd, vm, avgs in cursor.fetchall():
    vm = int(vm) if vm else 0
    avgs = float(avgs) if avgs else 0
    if cd and str(cd) <= f"{TARGET_YM}-31":
        cat = "closing"
    elif od and str(od) >= f"{TARGET_YEAR - 1}-01-01":
        cat = "new"
    elif vm >= 3 and avgs >= 30000:
        cat = "large_medium"
    else:
        cat = "small"
    cats[code] = dict(
        brand=brand, region=region, category=cat,
        opening_date=od, closing_date=cd,
        valid_months=vm, avg_sales=avgs,
    )

cc = Counter(v["category"] for v in cats.values())
print(f"  大中店: {cc.get('large_medium', 0)}, 小店: {cc.get('small', 0)}, "
      f"新店: {cc.get('new', 0)}, 关店: {cc.get('closing', 0)}")

# ─────────────────────────────────────
# Step 3: 获取所有门店月度数据
# ─────────────────────────────────────
print("Step 3: 获取月度数据")
all_codes = list(cats.keys())
store_m = defaultdict(list)
batch_size = 500
for i in range(0, len(all_codes), batch_size):
    batch = all_codes[i : i + batch_size]
    ph = ",".join(["%s"] * len(batch))
    sql = f"""
    SELECT m.store_code, m.`year_month`, m.sales_amount,
        CAST(SUBSTR(m.`year_month`, 6, 2) AS UNSIGNED) AS cm,
        CAST(SUBSTR(m.`year_month`, 1, 4) AS UNSIGNED) AS cy
    FROM store_monthly_metrics m
    WHERE m.store_code IN ({ph})
      AND m.`year_month` < '{TARGET_YM}' AND m.sales_amount > 0
      AND {SF_EXCLUDE}
    ORDER BY m.store_code, m.`year_month` DESC
    """
    cursor.execute(sql, batch)
    for code, ym, sales, cm, cy in cursor.fetchall():
        store_m[code].append((ym, float(sales), cm, cy))

print(f"  有数据门店: {len(store_m)}")

# ─────────────────────────────────────
# Step 4-7: 各类预估
# ─────────────────────────────────────
weights = [0.35, 0.25, 0.18, 0.12, 0.07, 0.03]

# 成熟店中位数（用于新店）
mature_medians = {}
mature_by_br = defaultdict(list)
for code, info in cats.items():
    if info["category"] == "large_medium" and info["avg_sales"] >= 30000:
        mature_by_br[(info["brand"], info["region"])].append(info["avg_sales"])
for key, avgs in mature_by_br.items():
    s = sorted(avgs)
    mature_medians[key] = s[len(s) // 2]

def get_ramp(om):
    if om <= 3:
        return 1.40
    if om <= 6:
        return 1.20
    if om <= 12:
        return 1.05
    return 1.00


preds = {}
for code, info in cats.items():
    cat = info["category"]
    months = store_m.get(code, [])
    b, r = info["brand"], info["region"]

    if cat == "large_medium":
        des = []
        for ym, s, cm, cy in months[:6]:
            sf = seasonal.get((b, r, cm), 1.0)
            des.append(s / sf if sf > 0 else s)
        if not des:
            preds[code] = 0
            continue
        w = weights[: len(des)]
        wa = sum(v * wt for v, wt in zip(des, w)) / max(sum(w), 0.01)
        tsf = seasonal.get((b, r, TARGET_MONTH), 1.0)
        preds[code] = wa * tsf

    elif cat == "small":
        des = []
        for ym, s, cm, cy in months[:3]:
            sf = seasonal.get((b, r, cm), 1.0)
            des.append(s / sf if sf > 0 else s)
        da = sum(des) / len(des) if des else 0
        tsf = seasonal.get((b, r, TARGET_MONTH), 1.0)
        preds[code] = da * tsf

    elif cat == "new":
        ref = mature_medians.get((b, r), 0)
        if ref == 0:
            for k, v in mature_medians.items():
                if k[0] == b:
                    ref = v
                    break
        od = info["opening_date"]
        if od:
            odt = datetime.strptime(str(od), "%Y-%m-%d")
            om = (TARGET_YEAR - odt.year) * 12 + (TARGET_MONTH - odt.month)
        else:
            om = 24
        preds[code] = ref * get_ramp(om)

    elif cat == "closing":
        des = []
        for ym, s, cm, cy in months[:3]:
            sf = seasonal.get((b, r, cm), 1.0)
            des.append(s / sf if sf > 0 else s)
        da = sum(des) / len(des) if des else 0
        tsf = seasonal.get((b, r, TARGET_MONTH), 1.0)
        base = da * tsf
        cd = info["closing_date"]
        if cd and str(cd)[:7] == TARGET_YM:
            td = calendar.monthrange(TARGET_YEAR, TARGET_MONTH)[1]
            od_d = int(str(cd)[-2:])
            preds[code] = base * (od_d / td) * 0.90
        else:
            preds[code] = base * 0.90
    else:
        preds[code] = 0

# ─────────────────────────────────────
# 汇总
# ─────────────────────────────────────
cat_totals = defaultdict(float)
cat_counts_pred = defaultdict(int)
for code, pred in preds.items():
    cat = cats[code]["category"]
    cat_totals[cat] += pred
    cat_counts_pred[cat] += 1

total = sum(preds.values())
api_ref = 779202773

print()
print("=" * 60)
print(f"预测汇总 ({TARGET_YM})")
print("=" * 60)
print(f"大中店: {cat_counts_pred['large_medium']:>5} 家, ¥{cat_totals['large_medium']:>15,.0f}")
print(f"小店:   {cat_counts_pred['small']:>5} 家, ¥{cat_totals['small']:>15,.0f}")
print(f"新店:   {cat_counts_pred['new']:>5} 家, ¥{cat_totals['new']:>15,.0f}")
print(f"关店:   {cat_counts_pred['closing']:>5} 家, ¥{cat_totals['closing']:>15,.0f}")
print("─" * 60)
print(f"总计:   {sum(cat_counts_pred.values()):>5} 家, ¥{total:>15,.0f}")
print()
print(f"API 参考值:            ¥{api_ref:>15,.0f}")
print(f"SQL 预测值:            ¥{total:>15,.0f}")
print(f"差异:                  ¥{total - api_ref:>15,.0f} ({(total - api_ref) / api_ref * 100:.2f}%)")

conn.close()

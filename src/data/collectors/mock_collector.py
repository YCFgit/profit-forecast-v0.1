"""Mock 数据采集器 — 用于开发和测试

生成 50+ 门店的模拟数据，覆盖 6 种门店分类：
大中店、小店、新店、虚拟店、临时特卖店、关店
"""

import random
from datetime import date, timedelta

import pandas as pd
from loguru import logger

from src.data.collectors.base import BaseCollector


class MockCollector(BaseCollector):
    """生成模拟数据，用于开发调试和单元测试"""

    STORE_COUNT = 55  # 模拟门店数

    # 品牌配置
    BRANDS = ["品牌A", "品牌B", "品牌C"]

    # 区域配置
    REGIONS = {
        "华东": ["上海", "杭州", "南京", "苏州"],
        "华南": ["广州", "深圳", "东莞", "佛山"],
        "华北": ["北京", "天津", "石家庄"],
        "华中": ["武汉", "长沙", "郑州"],
        "西南": ["成都", "重庆", "昆明"],
    }

    async def connect(self) -> None:
        logger.info("[Mock] 使用模拟数据源")

    async def disconnect(self) -> None:
        logger.info("[Mock] 断开模拟数据源")

    async def fetch_stores(self) -> pd.DataFrame:
        """生成模拟门店数据（50+ 门店，覆盖 6 种分类）"""
        random.seed(42)  # 固定种子保证可复现

        regions = list(self.REGIONS.keys())
        tiers = ["A", "B", "C", "D"]
        tier_weights = [0.15, 0.35, 0.35, 0.15]

        stores = []

        # 大中店（~25家）：业绩高、开业久
        for i in range(1, 26):
            region = regions[(i - 1) % len(regions)]
            city = random.choice(self.REGIONS[region])
            brand = self.BRANDS[(i - 1) % len(self.BRANDS)]
            tier = random.choices(tiers, weights=tier_weights, k=1)[0]
            area = random.uniform(150, 500)
            opening = date.today() - timedelta(days=random.randint(730, 2500))

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{city}{region}{'旗舰店' if tier == 'A' else '店'}{i:03d}",
                "brand": brand,
                "store_type": "direct",
                "region": region,
                "province": city,
                "city": city,
                "commercial_tier": tier,
                "store_area": round(area, 2),
                "opening_date": opening,
                "status": "active",
                "staff_count": random.randint(8, 20),
                "is_virtual": False,
                "is_temporary": False,
                "planned_closing_date": None,
            })

        # 小店（~15家）：业绩低、开业久
        for i in range(26, 41):
            region = regions[(i - 26) % len(regions)]
            city = random.choice(self.REGIONS[region])
            brand = self.BRANDS[(i - 26) % len(self.BRANDS)]
            tier = random.choice(["C", "D"])
            area = random.uniform(50, 120)
            opening = date.today() - timedelta(days=random.randint(730, 2500))

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{city}{region}小店{i:03d}",
                "brand": brand,
                "store_type": "direct",
                "region": region,
                "province": city,
                "city": city,
                "commercial_tier": tier,
                "store_area": round(area, 2),
                "opening_date": opening,
                "status": "active",
                "staff_count": random.randint(2, 5),
                "is_virtual": False,
                "is_temporary": False,
                "planned_closing_date": None,
            })

        # 新店（~5家）：开业不到1年
        for i in range(41, 46):
            region = regions[(i - 41) % len(regions)]
            city = random.choice(self.REGIONS[region])
            brand = self.BRANDS[(i - 41) % len(self.BRANDS)]
            opening = date.today() - timedelta(days=random.randint(30, 365))

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{city}{region}新店{i:03d}",
                "brand": brand,
                "store_type": "direct",
                "region": region,
                "province": city,
                "city": city,
                "commercial_tier": "B",
                "store_area": round(random.uniform(100, 300), 2),
                "opening_date": opening,
                "status": "active",
                "staff_count": random.randint(5, 12),
                "is_virtual": False,
                "is_temporary": False,
                "planned_closing_date": None,
            })

        # 虚拟店（~5家）
        for i in range(46, 51):
            region = regions[(i - 46) % len(regions)]
            brand = self.BRANDS[(i - 46) % len(self.BRANDS)]

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{brand}虚拟店{i:03d}",
                "brand": brand,
                "store_type": "virtual",
                "region": region,
                "province": "线上",
                "city": "线上",
                "commercial_tier": "C",
                "store_area": 0,
                "opening_date": date.today() - timedelta(days=random.randint(365, 1500)),
                "status": "active",
                "staff_count": 0,
                "is_virtual": True,
                "is_temporary": False,
                "planned_closing_date": None,
            })

        # 临时特卖店（~3家）
        for i in range(51, 54):
            region = regions[(i - 51) % len(regions)]
            city = random.choice(self.REGIONS[region])
            brand = self.BRANDS[(i - 51) % len(self.BRANDS)]

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{city}临时特卖{i:03d}",
                "brand": brand,
                "store_type": "temporary",
                "region": region,
                "province": city,
                "city": city,
                "commercial_tier": "D",
                "store_area": round(random.uniform(30, 80), 2),
                "opening_date": date.today() - timedelta(days=random.randint(30, 180)),
                "status": "active",
                "staff_count": random.randint(1, 3),
                "is_virtual": False,
                "is_temporary": True,
                "planned_closing_date": None,
            })

        # 关店（~2家）
        for i in range(54, 56):
            region = regions[(i - 54) % len(regions)]
            city = random.choice(self.REGIONS[region])
            brand = self.BRANDS[(i - 54) % len(self.BRANDS)]

            stores.append({
                "store_code": f"ST{i:04d}",
                "store_name": f"{city}关店{i:03d}",
                "brand": brand,
                "store_type": "direct",
                "region": region,
                "province": city,
                "city": city,
                "commercial_tier": "C",
                "store_area": round(random.uniform(80, 200), 2),
                "opening_date": date.today() - timedelta(days=random.randint(1000, 3000)),
                "status": "closed",
                "staff_count": 0,
                "is_virtual": False,
                "is_temporary": False,
                "planned_closing_date": date.today() - timedelta(days=random.randint(30, 90)),
            })

        df = pd.DataFrame(stores)
        logger.info(f"[Mock] 生成 {len(df)} 家门店数据")
        return df

    async def fetch_daily_sales(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """生成模拟日销数据"""
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        if end_date is None:
            end_date = date.today()

        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        categories = ["CAT_SHOES", "CAT_CLOTHING", "CAT_ACCESSORIES"]
        records = []

        # 新店开业效应系数
        def _promo_effect(days_since_open):
            months = days_since_open / 30.0
            if months <= 3:
                return 1.40
            elif months <= 6:
                return 1.20
            elif months <= 12:
                return 1.05
            else:
                return 1.00

        for code in store_codes:
            # 根据门店编号设置不同基础业绩
            store_num = int(code[2:])
            if store_num <= 25:
                base_daily = random.uniform(15000, 50000)  # 大中店
            elif store_num <= 40:
                base_daily = random.uniform(2000, 8000)    # 小店
            elif store_num <= 45:
                base_daily = random.uniform(8000, 25000)   # 新店
            elif store_num <= 50:
                base_daily = random.uniform(5000, 20000)   # 虚拟店
            elif store_num <= 53:
                base_daily = random.uniform(3000, 15000)   # 临时店
            else:
                base_daily = random.uniform(5000, 20000)   # 关店

            # 新店判定与开业日期
            is_new_store = 41 <= store_num <= 45
            store_opening = (
                date.today() - timedelta(days=random.randint(30, 365))
                if is_new_store
                else date.today() - timedelta(days=random.randint(730, 2500))
            )

            current = start_date
            while current <= end_date:
                month = current.month
                season_factor = {
                    1: 0.7, 2: 0.65, 3: 0.8, 4: 0.9, 5: 0.95, 6: 1.1,
                    7: 0.9, 8: 0.85, 9: 0.95, 10: 1.0, 11: 1.2, 12: 1.3,
                }[month]
                # 周末效应
                weekday_mult = 1.20 if current.weekday() >= 5 else 1.0
                # 新店开业效应
                days_open = (current - store_opening).days
                promo_mult = _promo_effect(max(0, days_open)) if is_new_store else 1.0

                for cat in categories:
                    cat_factor = {"CAT_SHOES": 1.0, "CAT_CLOTHING": 0.8, "CAT_ACCESSORIES": 0.4}[cat]
                    amount = base_daily * season_factor * weekday_mult * promo_mult * cat_factor * random.uniform(0.7, 1.3)
                    qty = max(1, int(amount / random.uniform(100, 500)))

                    records.append({
                        "store_code": code,
                        "sale_date": current,
                        "category_code": cat,
                        "channel_code": "CH_DIRECT",
                        "sales_amount": round(amount, 2),
                        "sales_qty": qty,
                        "avg_price": round(amount / qty, 2),
                        "return_amount": round(amount * random.uniform(0, 0.05), 2),
                        "return_qty": max(0, int(qty * random.uniform(0, 0.05))),
                        "customer_count": max(1, int(qty * random.uniform(1.2, 2.5))),
                    })
                current += timedelta(days=1)

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条日销数据 ({len(store_codes)} 家门店)")
        return df

    async def fetch_monthly_metrics(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """生成模拟月度指标（24个月）"""
        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        # 默认 24 个月数据
        if start_month is None:
            today = date.today()
            start_year = today.year - 2
            start_month = f"{start_year}-{today.month:02d}"

        records = []
        months = pd.date_range(
            start=start_month,
            end=end_month or date.today().strftime("%Y-%m"),
            freq="MS",
        )

        for code in store_codes:
            store_num = int(code[2:])
            # 根据门店类型设置基础业绩
            if store_num <= 25:
                base_sales = random.uniform(400000, 1500000)  # 大中店
            elif store_num <= 40:
                base_sales = random.uniform(50000, 150000)    # 小店
            elif store_num <= 45:
                base_sales = random.uniform(200000, 600000)   # 新店
            elif store_num <= 50:
                base_sales = random.uniform(100000, 400000)   # 虚拟店
            elif store_num <= 53:
                base_sales = random.uniform(80000, 300000)    # 临时店
            else:
                base_sales = random.uniform(100000, 500000)   # 关店

            for m in months:
                ym = m.strftime("%Y-%m")
                month = m.month
                # 季节波动
                season = {
                    1: 0.7, 2: 0.65, 3: 0.8, 4: 0.9, 5: 0.95, 6: 1.1,
                    7: 0.9, 8: 0.85, 9: 0.95, 10: 1.0, 11: 1.2, 12: 1.3,
                }[month]
                sales = base_sales * season * random.uniform(0.85, 1.15)
                margin = random.uniform(0.35, 0.60)

                records.append({
                    "store_code": code,
                    "year_month": ym,
                    "sales_amount": round(sales, 2),
                    "gross_profit": round(sales * margin, 2),
                    "gross_margin": round(margin, 4),
                    "sales_per_sqm": round(sales / random.uniform(80, 300), 2),
                    "revenue_per_staff": round(sales / random.randint(3, 12), 2),
                    "avg_ticket": round(random.uniform(150, 600), 2),
                    "return_rate": round(random.uniform(0, 0.08), 4),
                    "staff_count": random.randint(3, 15),
                })

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条月度指标")
        return df

    async def fetch_targets(
        self,
        store_codes: list[str] | None = None,
        target_type: str = "monthly",
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """生成模拟目标数据"""
        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        records = []
        for code in store_codes:
            records.append({
                "store_code": code,
                "target_type": target_type,
                "target_date": None,
                "target_month": target_month or date.today().strftime("%Y-%m"),
                "category_code": None,
                "sales_target": round(random.uniform(200000, 2000000), 2),
                "profit_target": round(random.uniform(50000, 500000), 2),
                "source": "system",
            })

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条目标数据")
        return df

    async def fetch_staff(self, store_codes: list[str] | None = None) -> pd.DataFrame:
        """生成模拟人员数据"""
        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        roles = ["manager", "supervisor", "staff", "staff", "staff", "trainee"]
        records = []
        for code in store_codes:
            count = random.randint(3, 12)
            for j in range(count):
                role = roles[j % len(roles)]
                records.append({
                    "store_code": code,
                    "staff_name": f"员工_{code}_{j+1:02d}",
                    "role": role,
                    "base_salary": round(random.uniform(3000, 12000), 2),
                    "commission_rate": round(random.uniform(0.01, 0.05), 4),
                    "hire_date": date.today() - timedelta(days=random.randint(30, 1500)),
                    "status": "active",
                })

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条人员数据")
        return df

    async def fetch_cost_structure(
        self,
        store_codes: list[str] | None = None,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> pd.DataFrame:
        """生成模拟成本结构数据"""
        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        records = []
        months = pd.date_range(
            start=start_month or "2024-01",
            end=end_month or date.today().strftime("%Y-%m"),
            freq="MS",
        )

        for code in store_codes:
            for m in months:
                ym = m.strftime("%Y-%m")
                revenue = random.uniform(150000, 1500000)
                records.append({
                    "store_code": code,
                    "year_month": ym,
                    "procurement_cost": round(revenue * random.uniform(0.35, 0.50), 2),
                    "labor_cost": round(revenue * random.uniform(0.10, 0.18), 2),
                    "rent_cost": round(revenue * random.uniform(0.08, 0.15), 2),
                    "logistics_cost": round(revenue * random.uniform(0.03, 0.06), 2),
                    "marketing_cost": round(revenue * random.uniform(0.02, 0.05), 2),
                    "commission_cost": round(revenue * random.uniform(0.01, 0.03), 2),
                    "other_cost": round(revenue * random.uniform(0.01, 0.03), 2),
                    "total_cost": round(revenue * random.uniform(0.60, 0.85), 2),
                })

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条成本数据")
        return df

    async def fetch_switch_status(
        self,
        target_month: str | None = None,
    ) -> pd.DataFrame:
        """生成模拟开关状态矩阵

        返回月度门店状态矩阵，格式：
        store_code, year_month, status ("on"/"off")

        基于 dws_pub.dws_dim_org_on_off 表的简化映射。
        """
        records = []
        today = date.today()

        # 生成近6个月的状态矩阵
        months = pd.date_range(
            end=today.strftime("%Y-%m"),
            periods=6,
            freq="MS",
        )

        # 关店门店（ST0054, ST0055）：最近3个月状态为 off
        cutoff = pd.Timestamp(today - timedelta(days=90))
        for i in range(54, 56):
            code = f"ST{i:04d}"
            for m in months:
                ym = m.strftime("%Y-%m")
                # 最近3个月为关闭状态
                if m >= cutoff:
                    records.append({
                        "store_code": code,
                        "year_month": ym,
                        "status": "off",
                    })
                else:
                    records.append({
                        "store_code": code,
                        "year_month": ym,
                        "status": "on",
                    })

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条开关状态数据")
        return df

    async def fetch_store_loss(
        self,
        store_codes: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """生成模拟门店日损益数据（每店独立成本比率）"""
        if store_codes is None:
            store_df = await self.fetch_stores()
            store_codes = store_df["store_code"].tolist()

        if start_date is None:
            start_date = date.today() - timedelta(days=180)
        if end_date is None:
            end_date = date.today()

        # 用门店编码做种子，保证每店有独立但稳定的成本比率
        rng = random.Random(42)

        # 季节系数
        season_map = {
            1: 0.70, 2: 0.65, 3: 0.80, 4: 0.90, 5: 0.95, 6: 1.10,
            7: 0.90, 8: 0.85, 9: 0.95, 10: 1.00, 11: 1.20, 12: 1.30,
        }

        records = []
        for code in store_codes:
            store_num = int(code[2:]) if code.startswith("ST") and code[2:].isdigit() else rng.randint(1, 60)

            # 基础日收入因门店类型而异
            if store_num <= 25:     # 大中店
                base_daily_rev = rng.uniform(15000, 50000)
            elif store_num <= 40:   # 小店
                base_daily_rev = rng.uniform(2000, 8000)
            elif store_num <= 45:   # 新店
                base_daily_rev = rng.uniform(8000, 25000)
            elif store_num <= 50:   # 虚拟店
                base_daily_rev = rng.uniform(5000, 20000)
            elif store_num <= 53:   # 临时特卖店
                base_daily_rev = rng.uniform(3000, 15000)
            else:                   # 关店等
                base_daily_rev = rng.uniform(5000, 20000)

            # 每店独立的成本比率
            cogs_ratio = rng.uniform(0.38, 0.52)
            salary_ratio = rng.uniform(0.08, 0.15)
            social_ratio = rng.uniform(0.03, 0.05)
            mall_fee_ratio = rng.uniform(0.02, 0.05)
            express_ratio = rng.uniform(0.005, 0.015)
            other_ratio = rng.uniform(0.005, 0.015)
            b_manage_ratio = rng.uniform(0.02, 0.04)

            # 新店开业效应系数（先高后低）
            def _promo_effect(days_since_open):
                months = days_since_open / 30.0
                if months <= 3:
                    return 1.40
                elif months <= 6:
                    return 1.20
                elif months <= 12:
                    return 1.05
                else:
                    return 1.00

            # 新店开业日期（ST0041-ST0045 近1年内开业）
            is_new_store = 41 <= store_num <= 45
            store_opening = (
                date.today() - timedelta(days=rng.randint(30, 365))
                if is_new_store
                else date.today() - timedelta(days=rng.randint(730, 2500))
            )

            current = start_date
            while current <= end_date:
                season = season_map.get(current.month, 1.0)
                # 周末效应
                weekday_mult = 1.20 if current.weekday() >= 5 else 1.0
                # 新店开业效应
                days_open = (current - store_opening).days
                promo_mult = _promo_effect(max(0, days_open)) if is_new_store else 1.0

                rev = base_daily_rev * season * weekday_mult * promo_mult * rng.uniform(0.8, 1.2)

                cogs = rev * cogs_ratio
                salary = rev * salary_ratio
                social = rev * social_ratio
                mall_fee = rev * mall_fee_ratio
                express = rev * express_ratio
                other_fee = rev * other_ratio
                b_manage = rev * b_manage_ratio
                decorate = rev * 0.005

                operating_exp = salary + social + mall_fee + express + other_fee + decorate
                gross_profit = rev - cogs
                operating_profit = gross_profit - operating_exp - b_manage

                # 返利口径（基于返利系数，不是随机噪声）
                rebate_factor = rng.uniform(0.93, 1.05)
                rebate_rev = rev * rebate_factor * rng.uniform(0.98, 1.02)
                rebate_cogs = cogs * rng.uniform(0.98, 1.02)
                rebate_gross = rebate_rev - rebate_cogs
                rebate_op = rebate_gross - operating_exp - b_manage

                records.append({
                    "store_code": code,
                    "sale_date": current,
                    "brand": f"品牌{chr(65 + (store_num - 1) % 3)}",
                    "store_name": f"门店{code}",
                    "region": ["华东", "华南", "华北", "华中", "西南"][(store_num - 1) % 5],
                    "actual_sales_pp": round(rev, 2),
                    "actual_sales": round(rev, 2),
                    "actual_cost": round(cogs, 2),
                    "actual_gross_profit": round(gross_profit, 2),
                    "actual_operating_expense": round(operating_exp, 2),
                    "actual_b_manage_expense": round(b_manage, 2),
                    "actual_operating_profit": round(operating_profit, 2),
                    "actual_mall_fee": round(mall_fee, 2),
                    "actual_salary": round(salary, 2),
                    "actual_social_fee": round(social, 2),
                    "actual_decorate_fee": round(decorate, 2),
                    "actual_express": round(express, 2),
                    "actual_other_fee": round(other_fee, 2),
                    "actual_store_contribution": round(operating_profit * 0.8, 2),
                    "rebate_sales": round(rebate_rev, 2),
                    "rebate_gross_profit": round(rebate_gross, 2),
                    "rebate_operating_profit": round(rebate_op, 2),
                    "budget_sales_pp": round(rev * rng.uniform(0.9, 1.1), 2),
                    "budget_operating_profit": round(operating_profit * rng.uniform(0.85, 1.15), 2),
                    "ly_sales_pp": round(rev * rng.uniform(0.85, 1.15), 2),
                    "ly_operating_profit": round(operating_profit * rng.uniform(0.8, 1.2), 2),
                })
                current += timedelta(days=1)

        df = pd.DataFrame(records)
        logger.info(f"[Mock] 生成 {len(df)} 条门店日损益数据（{len(store_codes)} 家门店）")
        return df

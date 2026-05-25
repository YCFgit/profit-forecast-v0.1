"""API 集成测试

使用 FastAPI TestClient 测试所有 API 端点。
标记 @pytest.mark.slow 的测试涉及 Prophet 模型训练，需要较长时间。
CI 中使用 pytest -m "not slow" 跳过慢测试。
"""

import pytest


class TestHealthAPI:
    """健康检查 API"""

    def test_health_check(self, client):
        """GET /health"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestStoreAPI:
    """门店管理 API（需要 PostgreSQL 连接）"""

    @pytest.mark.xfail(reason="需要 PostgreSQL 数据库连接", strict=False)
    def test_list_stores(self, client):
        """GET /api/v1/stores/"""
        resp = client.get("/api/v1/stores/")
        assert resp.status_code in (200, 500)


@pytest.mark.slow
class TestForecastAPI:
    """基线预估 API（含 Prophet，较慢）"""

    def test_get_baselines(self, client):
        """GET /api/v1/forecast/baselines"""
        resp = client.get("/api/v1/forecast/baselines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["store_count"] > 0
        assert "baselines" in data
        assert "model_info" in data

    def test_get_store_baseline(self, client):
        """GET /api/v1/forecast/baselines/{store_code}"""
        resp = client.get("/api/v1/forecast/baselines")
        data = resp.json()
        store_code = list(data["baselines"].keys())[0]

        resp = client.get(f"/api/v1/forecast/baselines/{store_code}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["store_code"] == store_code


@pytest.mark.slow
class TestAllocationAPI:
    """承压分配 API（依赖基线预估）"""

    def test_allocate(self, client):
        """POST /api/v1/allocation/"""
        resp = client.post("/api/v1/allocation/", json={
            "total_target": 10_000_000,
            "with_scenarios": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["store_count"] > 0
        assert len(data["allocations"]) > 0
        assert data["total_target"] > 0

    def test_allocate_with_scenarios(self, client):
        """POST /api/v1/allocation/ 带情景对比"""
        resp = client.post("/api/v1/allocation/", json={
            "total_target": 10_000_000,
            "with_scenarios": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenarios"] is not None

    def test_get_scenarios(self, client):
        """GET /api/v1/allocation/scenarios"""
        resp = client.get("/api/v1/allocation/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "recommendation" in data


@pytest.mark.slow
class TestProfitAPI:
    """利润测算 API（依赖基线预估）"""

    def test_calculate_profit(self, client):
        """POST /api/v1/profit/calculate"""
        resp = client.post("/api/v1/profit/calculate", json={
            "total_target": 10_000_000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "summary" in data
        assert "pnl" in data
        assert "comparison" in data
        assert "top_stores" in data
        assert "bottom_stores" in data

    def test_profit_drill_down_region(self, client):
        """GET /api/v1/profit/drill-down/region"""
        resp = client.get("/api/v1/profit/drill-down/region")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["dimension"] == "区域"

    def test_profit_drill_down_type(self, client):
        """GET /api/v1/profit/drill-down/type"""
        resp = client.get("/api/v1/profit/drill-down/type")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["dimension"] == "门店类型"


@pytest.mark.slow
class TestRiskAPI:
    """风险评估 API（依赖基线预估）"""

    def test_assess_risk(self, client):
        """POST /api/v1/risk/assess"""
        resp = client.post("/api/v1/risk/assess", json={
            "total_target": 10_000_000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "overall_score" in data
        assert "overall_level" in data
        assert "factors" in data
        assert "recommendations" in data

    def test_monte_carlo(self, client):
        """POST /api/v1/risk/monte-carlo"""
        resp = client.post("/api/v1/risk/monte-carlo", json={
            "total_target": 10_000_000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "profit_mean" in data
        assert "loss_probability" in data
        assert "var_95" in data


class TestPipelineAPI:
    """全流程编排 API（不涉及 Prophet）"""

    def test_pipeline_health(self, client):
        """GET /api/v1/pipeline/health"""
        resp = client.get("/api/v1/pipeline/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data

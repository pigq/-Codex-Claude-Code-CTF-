import httpx
from fastapi.testclient import TestClient

from web.backend.api import DEFAULT_MUGGLE_LEADS_ENDPOINT
from web.backend.main import app


def test_cooperation_intent_uses_author_default_endpoint(monkeypatch):
    sent = {}

    class MockAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            sent["url"] = url
            sent["json"] = json
            return httpx.Response(200, json={"success": True})

    monkeypatch.delenv("MUGGLE_LEADS_ENDPOINT", raising=False)
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    client = TestClient(app)

    response = client.post(
        "/api/cooperation/intent",
        json={
            "intent_type": "ads",
            "name": "测试用户",
            "contact": "wechat:test",
            "message": "想咨询广告位合作",
        },
    )

    assert response.status_code == 200
    assert sent["url"] == DEFAULT_MUGGLE_LEADS_ENDPOINT
    assert sent["json"]["source_id"] == "codex-session-patcher"


def test_cooperation_intent_forwards_to_muggle_leads(monkeypatch):
    sent = {}

    class MockAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            sent["url"] = url
            sent["json"] = json
            return httpx.Response(200, json={"success": True})

    monkeypatch.setenv("MUGGLE_LEADS_ENDPOINT", "https://leads.example/api/sources/codex-session-patcher/intents")
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    client = TestClient(app)

    response = client.post(
        "/api/cooperation/intent",
        json={
            "intent_type": "token_supply",
            "name": "张三",
            "contact": "tg:@demo",
            "message": "需要了解 AI 中转站 Token 批发供应",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "已提交，我会尽快联系你。"}
    assert sent["url"] == "https://leads.example/api/sources/codex-session-patcher/intents"
    assert sent["json"]["source_id"] == "codex-session-patcher"
    assert sent["json"]["source_name"] == "Codex Session Patcher"
    assert sent["json"]["source_version"]
    assert sent["json"]["intent_type"] == "token_supply"
    assert sent["json"]["intent_type_label"] == "AI 中转站 Token 批发供应"
    assert sent["json"]["name"] == "张三"


def test_cooperation_intent_reports_remote_failure(monkeypatch):
    class MockAsyncClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json):
            return httpx.Response(429, json={"success": False, "message": "提交太频繁，请稍后再试"})

    monkeypatch.setenv("MUGGLE_LEADS_ENDPOINT", "https://leads.example/api/sources/codex-session-patcher/intents")
    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    client = TestClient(app)

    response = client.post(
        "/api/cooperation/intent",
        json={
            "intent_type": "development",
            "name": "张三",
            "contact": "qq:89045349",
            "message": "需要项目开发合作",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "提交太频繁，请稍后再试"

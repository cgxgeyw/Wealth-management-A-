from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.data_source import (
    AnnouncementItem,
    AnnouncementResponse,
    KlineBar,
    KlineResponse,
    NewsItem,
    NewsResponse,
    RealtimeQuote,
    ResearchReportItem,
    ResearchReportResponse,
)


def test_agent_config_update_render_and_rollback() -> None:
    with TestClient(app) as client:
        listed = client.get("/api/agents")
        assert listed.status_code == 200
        agents = listed.json()["items"]
        assert any(item["key"] == "technical" for item in agents)

        original = client.get("/api/agents/technical").json()
        original_version = original["current_version"]

        updated = client.patch(
            "/api/agents/technical",
            json={
                "temperature": 0.3,
                "task_prompt": "分析 {{stock_code}} 的技术结构。",
                "variables": ["{{stock_code}}"],
                "tools": ["行情数据", "技术指标"],
                "change_note": "测试更新",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["current_version"] == original_version + 1

        rendered = client.post(
            "/api/agents/technical/render",
            json={"variables": {"stock_code": "300750"}},
        )
        assert rendered.status_code == 200
        assert "300750" in rendered.json()["rendered_task_prompt"]
        assert rendered.json()["missing_variables"] == []

        versions = client.get("/api/agents/technical/versions")
        assert versions.status_code == 200
        assert versions.json()["items"][0]["change_note"] == "测试更新"

        rollback = client.post(
            "/api/agents/technical/rollback",
            json={"version": original_version, "change_note": "测试回滚"},
        )
        assert rollback.status_code == 200
        assert rollback.json()["task_prompt"] == original["task_prompt"]


def test_agent_test_run_preview() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/agents/news/test-run",
            json={"input_text": "测试输入", "variables": {"stock_code": "300750", "stock_name": "宁德时代"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "preview_only"
    assert body["estimated_tokens"] > 0


def test_agent_tool_registry_and_document_write() -> None:
    with TestClient(app) as client:
        registry = client.get("/api/agent-tools")
        assert registry.status_code == 200
        tools = registry.json()["items"]
        assert any(item["key"] == "document.write" and item["enabled"] for item in tools)

        client.patch(
            "/api/agents/research_director",
            json={"tools": ["document.write"], "change_note": "enable document tool"},
        )
        response = client.post(
            "/api/agent-tools/research_director/document.write/run",
            json={
                "params": {
                    "title": "300750 测试报告",
                    "topic": "300750",
                    "summary": "用于验证文档工具可以真实生成文件。",
                    "sections": [{"heading": "结论", "bullets": ["工具执行成功"]}],
                    "references": ["pytest"],
                }
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["output"]["path"].endswith(".md")
    assert "工具执行成功" in body["output"]["content"]
    Path(body["output"]["path"]).unlink(missing_ok=True)


def test_agent_tool_permission_denied() -> None:
    with TestClient(app) as client:
        client.patch(
            "/api/agents/technical",
            json={"tools": ["stock.quote"], "change_note": "restrict tools"},
        )
        response = client.post(
            "/api/agent-tools/technical/document.write/run",
            json={"params": {"title": "未授权", "topic": "300750"}},
        )

    assert response.status_code == 403


def test_agent_market_tools_execute_with_permissions(monkeypatch) -> None:
    def fake_quote(db, symbol: str) -> RealtimeQuote:
        return RealtimeQuote(
            symbol=symbol,
            name="宁德时代",
            price=300.5,
            change_percent=1.2,
            timestamp="2026-07-08 15:00:00",
            provider_key="pytest",
        )

    def fake_klines(db, symbol: str, period: str = "daily", limit: int = 120, adjust: str = "qfq") -> KlineResponse:
        bars = [
            KlineBar(
                time=f"2026-07-{day:02d}",
                open=100 + day,
                close=101 + day,
                high=102 + day,
                low=99 + day,
                volume=10000 + day,
                amount=1000000 + day,
            )
            for day in range(1, 35)
        ]
        return KlineResponse(symbol=symbol, name="宁德时代", period=period, provider_key="pytest", items=bars[-limit:])

    monkeypatch.setattr("app.services.agent_tools.get_realtime_quote", fake_quote)
    monkeypatch.setattr("app.services.agent_tools.get_klines", fake_klines)

    with TestClient(app) as client:
        registry = client.get("/api/agent-tools")
        assert registry.status_code == 200
        enabled_keys = {item["key"] for item in registry.json()["items"] if item["enabled"]}
        assert {"stock.quote", "stock.bars", "stock.indicators"}.issubset(enabled_keys)

        client.patch(
            "/api/agents/technical",
            json={
                "tools": ["stock.quote", "stock.bars", "stock.indicators"],
                "change_note": "enable market tools",
            },
        )
        quote = client.post(
            "/api/agent-tools/technical/stock.quote/run",
            json={"params": {"symbol": "300750"}},
        )
        bars = client.post(
            "/api/agent-tools/technical/stock.bars/run",
            json={"params": {"symbol": "300750", "period": "daily", "limit": 5}},
        )
        indicators = client.post(
            "/api/agent-tools/technical/stock.indicators/run",
            json={"params": {"symbol": "300750", "names": ["ma", "macd"], "limit": 30}},
        )

    assert quote.status_code == 200
    assert quote.json()["output"]["price"] == 300.5
    assert bars.status_code == 200
    assert len(bars.json()["output"]["items"]) == 5
    assert indicators.status_code == 200
    indicator_names = {item["name"] for item in indicators.json()["output"]["items"]}
    assert {"MA5", "DIF", "DEA", "MACD"}.issubset(indicator_names)


def test_agent_news_tools_execute_with_permissions(monkeypatch) -> None:
    def fake_market_news(db, limit: int = 30) -> NewsResponse:
        return NewsResponse(
            provider_key="pytest",
            items=[
                NewsItem(
                    id="1",
                    title="宁德时代发布储能进展",
                    content="300750 相关",
                    source="pytest",
                    related_stocks=["300750"],
                ),
                NewsItem(id="2", title="无关新闻", content="其他公司", source="pytest"),
            ],
        )

    def fake_announcements(db, symbol: str, limit: int = 20) -> AnnouncementResponse:
        return AnnouncementResponse(
            symbol=symbol,
            provider_key="pytest",
            items=[
                AnnouncementItem(id="ann-1", symbol=symbol, title="年度权益分派公告", source="pytest"),
            ],
        )

    def fake_reports(db, symbol: str, limit: int = 10) -> ResearchReportResponse:
        return ResearchReportResponse(
            symbol=symbol,
            provider_key="pytest",
            items=[
                ResearchReportItem(id="rep-1", title="宁德时代深度报告", stock_code=symbol, org_name="pytest"),
            ],
        )

    monkeypatch.setattr("app.services.agent_tools.get_market_news", fake_market_news)
    monkeypatch.setattr("app.services.agent_tools.get_announcements", fake_announcements)
    monkeypatch.setattr("app.services.agent_tools.get_research_reports", fake_reports)

    with TestClient(app) as client:
        registry = client.get("/api/agent-tools")
        assert registry.status_code == 200
        enabled_keys = {item["key"] for item in registry.json()["items"] if item["enabled"]}
        assert {"stock.news", "stock.announcements", "stock.research_reports"}.issubset(enabled_keys)

        client.patch(
            "/api/agents/news",
            json={
                "tools": ["stock.news", "stock.announcements", "stock.research_reports"],
                "change_note": "enable news tools",
            },
        )
        news = client.post(
            "/api/agent-tools/news/stock.news/run",
            json={"params": {"symbol": "300750", "limit": 10}},
        )
        announcements = client.post(
            "/api/agent-tools/news/stock.announcements/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )
        reports = client.post(
            "/api/agent-tools/news/stock.research_reports/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )

    assert news.status_code == 200
    news_items = news.json()["output"]["items"]
    assert len(news_items) == 1
    assert news_items[0]["id"] == "1"
    assert announcements.status_code == 200
    assert announcements.json()["output"]["items"][0]["title"] == "年度权益分派公告"
    assert reports.status_code == 200
    assert reports.json()["output"]["items"][0]["title"] == "宁德时代深度报告"

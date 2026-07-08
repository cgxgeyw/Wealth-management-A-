from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.data_source import (
    AnnouncementItem,
    AnnouncementResponse,
    DragonTigerItem,
    DragonTigerResponse,
    FinancialStatementResponse,
    FinancialStatementRow,
    FundamentalMetric,
    FundamentalResponse,
    FundFlowItem,
    FundFlowResponse,
    KlineBar,
    KlineResponse,
    LockupExpiryItem,
    LockupExpiryResponse,
    MarginTradingItem,
    MarginTradingResponse,
    MacroIndicatorItem,
    MacroIndicatorResponse,
    NewsItem,
    NewsResponse,
    NorthboundFlowItem,
    NorthboundFlowResponse,
    RealtimeQuote,
    ResearchReportItem,
    ResearchReportResponse,
    SectorSnapshotItem,
    SectorSnapshotResponse,
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


def test_agent_fundamental_and_capital_tools_execute_with_permissions(monkeypatch) -> None:
    def fake_fundamentals(db, symbol: str) -> FundamentalResponse:
        return FundamentalResponse(
            symbol=symbol,
            name="宁德时代",
            provider_key="pytest",
            metrics=[FundamentalMetric(key="pe_ttm", label="市盈率TTM", value=22.5)],
        )

    def fake_financial_statements(
        db,
        symbol: str,
        statement_type: str = "income",
        limit: int = 4,
    ) -> FinancialStatementResponse:
        return FinancialStatementResponse(
            symbol=symbol,
            statement_type=statement_type,
            provider_key="pytest",
            items=[
                FinancialStatementRow(
                    report_date="2025-12-31",
                    values={"revenue": 1000.0, "net_profit": 120.0},
                )
            ],
        )

    def fake_fund_flow(db, symbol: str, limit: int = 20) -> FundFlowResponse:
        return FundFlowResponse(
            symbol=symbol,
            name="宁德时代",
            provider_key="pytest",
            items=[FundFlowItem(date="2026-07-08", main_net_inflow=1000000.0)],
        )

    def fake_northbound_flow(db, limit: int = 20) -> NorthboundFlowResponse:
        return NorthboundFlowResponse(
            provider_key="pytest",
            items=[NorthboundFlowItem(trade_date="2026-07-08", mutual_type="沪深股通", net_deal_amount=12.3)],
        )

    def fake_dragon_tiger(db, symbol: str, limit: int = 10) -> DragonTigerResponse:
        return DragonTigerResponse(
            symbol=symbol,
            provider_key="pytest",
            items=[DragonTigerItem(trade_date="2026-07-08", symbol=symbol, reason="涨幅偏离值达7%")],
        )

    def fake_lockup_expiry(db, symbol: str, limit: int = 10) -> LockupExpiryResponse:
        return LockupExpiryResponse(
            symbol=symbol,
            provider_key="pytest",
            items=[LockupExpiryItem(free_date="2026-08-01", symbol=symbol, shares=10000.0)],
        )

    def fake_margin_trading(db, symbol: str, limit: int = 10) -> MarginTradingResponse:
        return MarginTradingResponse(
            symbol=symbol,
            provider_key="pytest",
            items=[MarginTradingItem(date="2026-07-08", symbol=symbol, margin_balance=2000000.0)],
        )

    monkeypatch.setattr("app.services.agent_tools.get_fundamentals", fake_fundamentals)
    monkeypatch.setattr("app.services.agent_tools.get_financial_statements", fake_financial_statements)
    monkeypatch.setattr("app.services.agent_tools.get_fund_flow", fake_fund_flow)
    monkeypatch.setattr("app.services.agent_tools.get_northbound_flow", fake_northbound_flow)
    monkeypatch.setattr("app.services.agent_tools.get_dragon_tiger", fake_dragon_tiger)
    monkeypatch.setattr("app.services.agent_tools.get_lockup_expiry", fake_lockup_expiry)
    monkeypatch.setattr("app.services.agent_tools.get_margin_trading", fake_margin_trading)

    tool_keys = [
        "stock.fundamentals",
        "stock.financial_statements",
        "stock.fund_flow",
        "market.northbound_flow",
        "stock.dragon_tiger",
        "stock.lockup_expiry",
        "stock.margin_trading",
    ]

    with TestClient(app) as client:
        registry = client.get("/api/agent-tools")
        assert registry.status_code == 200
        enabled_keys = {item["key"] for item in registry.json()["items"] if item["enabled"]}
        assert set(tool_keys).issubset(enabled_keys)

        client.patch(
            "/api/agents/capital_flow",
            json={"tools": tool_keys, "change_note": "enable capital tools"},
        )
        fundamentals = client.post(
            "/api/agent-tools/capital_flow/stock.fundamentals/run",
            json={"params": {"symbol": "300750"}},
        )
        statements = client.post(
            "/api/agent-tools/capital_flow/stock.financial_statements/run",
            json={"params": {"symbol": "300750", "statement_type": "income", "limit": 2}},
        )
        fund_flow = client.post(
            "/api/agent-tools/capital_flow/stock.fund_flow/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )
        northbound = client.post(
            "/api/agent-tools/capital_flow/market.northbound_flow/run",
            json={"params": {"limit": 5}},
        )
        dragon_tiger = client.post(
            "/api/agent-tools/capital_flow/stock.dragon_tiger/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )
        lockup = client.post(
            "/api/agent-tools/capital_flow/stock.lockup_expiry/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )
        margin = client.post(
            "/api/agent-tools/capital_flow/stock.margin_trading/run",
            json={"params": {"symbol": "300750", "limit": 5}},
        )

    assert fundamentals.status_code == 200
    assert fundamentals.json()["output"]["metrics"][0]["key"] == "pe_ttm"
    assert statements.status_code == 200
    assert statements.json()["output"]["items"][0]["values"]["revenue"] == 1000.0
    assert fund_flow.status_code == 200
    assert fund_flow.json()["output"]["items"][0]["main_net_inflow"] == 1000000.0
    assert northbound.status_code == 200
    assert northbound.json()["output"]["items"][0]["net_deal_amount"] == 12.3
    assert dragon_tiger.status_code == 200
    assert dragon_tiger.json()["output"]["items"][0]["reason"] == "涨幅偏离值达7%"
    assert lockup.status_code == 200
    assert lockup.json()["output"]["items"][0]["shares"] == 10000.0
    assert margin.status_code == 200
    assert margin.json()["output"]["items"][0]["margin_balance"] == 2000000.0


def test_agent_macro_and_quality_tools_execute_with_permissions(monkeypatch) -> None:
    def fake_sector_snapshots(db, sector_type: str = "industry", limit: int = 20) -> SectorSnapshotResponse:
        return SectorSnapshotResponse(
            provider_key="pytest",
            items=[
                SectorSnapshotItem(
                    code="BK0428",
                    name="电池",
                    change_percent=2.3,
                    sector_type=sector_type,
                )
            ],
        )

    def fake_macro_indicator(db, indicator: str = "cpi", limit: int = 12) -> MacroIndicatorResponse:
        return MacroIndicatorResponse(
            indicator=indicator,
            provider_key="pytest",
            items=[MacroIndicatorItem(report_date="2026-06", values={"value": 1.5})],
        )

    monkeypatch.setattr("app.services.agent_tools.get_sector_snapshots", fake_sector_snapshots)
    monkeypatch.setattr("app.services.agent_tools.get_macro_indicator", fake_macro_indicator)

    tool_keys = ["data.quality", "sector.snapshots", "market.macro"]
    with TestClient(app) as client:
        registry = client.get("/api/agent-tools")
        assert registry.status_code == 200
        enabled_keys = {item["key"] for item in registry.json()["items"] if item["enabled"]}
        assert set(tool_keys).issubset(enabled_keys)

        client.patch(
            "/api/agents/policy_industry",
            json={"tools": tool_keys, "change_note": "enable macro tools"},
        )
        quality = client.post(
            "/api/agent-tools/policy_industry/data.quality/run",
            json={"params": {"log_limit": 20}},
        )
        sectors = client.post(
            "/api/agent-tools/policy_industry/sector.snapshots/run",
            json={"params": {"sector_type": "industry", "limit": 5}},
        )
        macro = client.post(
            "/api/agent-tools/policy_industry/market.macro/run",
            json={"params": {"indicator": "cpi", "limit": 5}},
        )

    assert quality.status_code == 200
    assert quality.json()["output"]["items"]
    assert "provider_key" in quality.json()["output"]["items"][0]
    assert sectors.status_code == 200
    assert sectors.json()["output"]["items"][0]["name"] == "电池"
    assert macro.status_code == 200
    assert macro.json()["output"]["items"][0]["values"]["value"] == 1.5


def test_agent_run_orchestrates_allowed_tools(monkeypatch) -> None:
    def fake_execute_tool(db, tool_key: str, params: dict) -> dict:
        if tool_key == "stock.quote":
            return {"symbol": params["symbol"], "price": 300.5, "provider_key": "pytest"}
        if tool_key == "stock.indicators":
            return {"symbol": params["symbol"], "items": [{"name": "MACD", "values": [0.1, 0.2]}]}
        return {"ok": True}

    monkeypatch.setattr("app.services.agent_orchestrator.execute_tool", fake_execute_tool)

    with TestClient(app) as client:
        client.patch(
            "/api/agents/technical",
            json={
                "tools": ["stock.quote", "stock.indicators"],
                "change_note": "orchestration test tools",
            },
        )
        created = client.post(
            "/api/agent-runs",
            json={
                "symbol": "300750",
                "query": "测试技术面工具编排",
                "agent_keys": ["technical"],
                "period": "daily",
                "limit": 30,
            },
        )

        assert created.status_code == 200
        body = created.json()
        run_key = body["run_key"]
        listed = client.get("/api/agent-runs")
        fetched = client.get(f"/api/agent-runs/{run_key}")

    assert body["status"] == "completed"
    assert body["symbol"] == "300750"
    assert body["agent_keys"] == ["technical"]
    assert [step["tool_key"] for step in body["steps"]] == ["stock.quote", "stock.indicators"]
    assert body["result"]["tool_success_count"] == 2
    assert listed.status_code == 200
    assert any(item["run_key"] == run_key for item in listed.json()["items"])
    assert fetched.status_code == 200
    assert fetched.json()["run_key"] == run_key

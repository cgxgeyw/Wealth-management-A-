import json
from pathlib import Path
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.services.agent_skills import assigned_skill_catalog, assigned_skill_instructions, load_assigned_skill
from app.services.agent_orchestrator import _normalize_final_artifact, _parse_json_object
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
    DataSnapshotRead,
)
from app.schemas.agent_run import AgentRunRead
from app.schemas.analysis_task import AnalysisTaskCreateRequest
from app.services.analysis_tasks import run_analysis_task_inline


def fake_snapshot(snapshot_id: int = 901) -> DataSnapshotRead:
    return DataSnapshotRead(
        id=snapshot_id,
        symbol="300750",
        period="daily",
        snapshot_type="analysis_context",
        snapshot_json='{"symbol":"300750","warnings":[]}',
        created_at=datetime.now(),
    )


def valid_pipeline_result(title: str = "测试分析报告") -> dict:
    markdown = (
        f"# {title}\n\n"
        "## 结论\n\n基于已获取且可追溯的证据，当前应保持审慎观察。\n\n"
        "## 关键依据\n\n- 行情与事件数据已经由专业 Agent 获取并形成阶段结论。\n"
        "- 投研总监对上游证据进行了综合，而不是使用工具调用计数代替分析。\n\n"
        "## 主要风险\n\n- 数据时效性和外部事件可能改变当前判断。\n\n"
        "## 后续观察\n\n- 继续跟踪价格、成交量和公告变化，并在证据失效时重新评估。\n"
        "- 若关键证据发生反转，应停止沿用本报告结论并重新运行完整工作流。\n"
    )
    return {
        "title": title,
        "conclusion": "审慎观察",
        "horizon": "短线",
        "confidence": 68,
        "key_evidence": ["行情与事件证据已形成阶段结论"],
        "risks": ["数据时效性风险"],
        "watch_items": ["价格、成交量和公告变化"],
        "summary": "投研总监已综合上游阶段产物。",
        "markdown_report": markdown,
        "agent_summaries": [],
        "quality_gate": {"passed": True, "errors": []},
    }


def test_agent_artifact_json_repair_and_normalization() -> None:
    malformed = """模型分析完成：
```json
{'title': '比亚迪分析', 'confidence': '中（65-70%）', 'risks': ['追高风险',],}
```
"""

    parsed = _parse_json_object(malformed)
    normalized = _normalize_final_artifact({
        **parsed,
        "horizon": {
            "short_term": "谨慎观察（1-2周）",
            "medium_term": "偏多布局（1-3个月）",
        },
    })

    assert normalized["title"] == "比亚迪分析"
    assert normalized["confidence"] == 68
    assert normalized["risks"] == ["追高风险"]
    assert normalized["horizon"] == "短期：谨慎观察（1-2周）；中期：偏多布局（1-3个月）"


def test_analysis_task_lifecycle_and_report(monkeypatch, tmp_path) -> None:
    report_path = tmp_path / "analysis-report.md"
    report_path.write_text("# 测试报告\n\n- 已生成\n", encoding="utf-8")

    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=42,
            run_key="AR-PYTEST",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=902,
            agent_keys=payload.agent_keys,
            steps=[
                {
                    "agent_key": "research_director",
                    "agent_name": "投研总监",
                    "tool_key": "document.write",
                    "status": "success",
                    "params": {},
                    "output_preview": {"summary": "document 20 chars", "path": str(report_path)},
                    "error": "",
                }
            ],
            result=valid_pipeline_result(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)

    with TestClient(app) as client:
        created = client.post(
            "/api/analysis-tasks",
            json={
                "symbol": "300750",
                "query": "生成测试报告",
                "agent_keys": ["research_director"],
                "include_report": True,
            },
        )
        task_key = created.json()["task_key"]
        listed = client.get("/api/analysis-tasks?limit=5")
        detail = client.get(f"/api/analysis-tasks/{task_key}")
        execution = client.get(f"/api/analysis-tasks/{task_key}/execution")
        report = client.get(f"/api/analysis-tasks/{task_key}/report")
        download = client.get(f"/api/analysis-tasks/{task_key}/report/download")
        deleted = client.delete(f"/api/analysis-tasks/{task_key}")
        missing = client.get(f"/api/analysis-tasks/{task_key}")

    assert created.status_code == 200
    assert created.json()["status"] == "pending"
    assert created.json()["workflow"]["agents"][0]["key"] == "research_director"
    assert listed.status_code == 200
    assert any(item["task_key"] == task_key for item in listed.json()["items"])
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    assert detail.json()["run_key"] == "AR-PYTEST"
    assert detail.json()["snapshot_id"] == 902
    assert detail.json()["report_format"] == "markdown"
    assert execution.status_code == 200
    assert [item["event_type"] for item in execution.json()["items"]] == [
        "task_started", "report_validated", "report_saved", "task_completed"
    ]
    assert report.status_code == 200
    assert "测试报告" in report.json()["content"]
    assert download.status_code == 200
    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert not report_path.exists()


def test_analysis_task_records_can_clear_finished_tasks(monkeypatch) -> None:
    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=46,
            run_key="AR-CLEAR",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=0,
            agent_keys=payload.agent_keys,
            steps=[
                {
                    "agent_key": "technical",
                    "agent_name": "技术面",
                    "tool_key": "stock.quote",
                    "status": "success",
                    "params": {"symbol": payload.symbol},
                    "output_preview": {},
                    "error": "",
                }
            ],
            result={"conclusion": "完成"},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)
    with TestClient(app) as client:
        created = client.post(
            "/api/analysis-tasks",
            json={"symbol": "300750", "query": "清理测试", "agent_keys": ["technical"]},
        )
        task_key = created.json()["task_key"]
        cleared = client.delete("/api/analysis-tasks")
        missing = client.get(f"/api/analysis-tasks/{task_key}")

    assert cleared.status_code == 200
    assert cleared.json()["deleted_count"] >= 1
    assert missing.status_code == 404


def test_analysis_task_can_start_without_single_stock_target(monkeypatch) -> None:
    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=45,
            run_key="AR-MARKET",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=905,
            agent_keys=payload.agent_keys,
            steps=[
                {
                    "agent_key": "policy_industry",
                    "agent_name": "政策行业",
                    "tool_key": "market.macro",
                    "status": "success",
                    "params": {"indicator": "cpi", "limit": 12},
                    "output_preview": {"summary": "1 metrics"},
                    "error": "",
                }
            ],
            result=valid_pipeline_result("本周市场风险与板块机会分析报告"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)

    with TestClient(app) as client:
        created = client.post(
            "/api/analysis-tasks",
            json={"query": "分析本周市场风险与板块机会", "agent_keys": ["policy_industry"]},
        )
        detail = client.get(f"/api/analysis-tasks/{created.json()['task_key']}")

    assert created.status_code == 200
    assert created.json()["symbol"] == ""
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    assert detail.json()["query"] == "分析本周市场风险与板块机会"


def test_analysis_task_always_generates_markdown_report(monkeypatch, tmp_path) -> None:
    report_path = tmp_path / "automatic-report.md"

    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=47,
            run_key="AR-AUTO-REPORT",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=0,
            agent_keys=payload.agent_keys,
            steps=[],
            result=valid_pipeline_result("自动报告"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def fake_write_document(db, tool_key: str, params: dict) -> dict:
        assert tool_key == "document.write"
        assert params["content"].startswith("# 自动报告")
        report_path.write_text("# 自动报告\n", encoding="utf-8")
        return {"path": str(report_path), "content": "# 自动报告\n"}

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)
    monkeypatch.setattr("app.services.analysis_tasks.execute_tool", fake_write_document)
    with TestClient(app) as client:
        created = client.post(
            "/api/analysis-tasks",
            json={"query": "检查自动报告", "mode": "quick", "include_report": False},
        )
        detail = client.get(f"/api/analysis-tasks/{created.json()['task_key']}")
        report = client.get(f"/api/analysis-tasks/{created.json()['task_key']}/report")

    assert created.status_code == 200
    assert detail.json()["report_format"] == "markdown"
    assert detail.json()["report_path"] == str(report_path)
    assert report.json()["content"] == "# 自动报告\n"


def test_analysis_task_rejects_incomplete_final_artifact(monkeypatch) -> None:
    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=48,
            run_key="AR-INVALID-REPORT",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="failed",
            snapshot_id=0,
            agent_keys=payload.agent_keys,
            steps=[],
            result={
                "agent_summaries": [{"agent_key": "research_director", "agent_name": "投研总监", "status": "failed"}],
                "quality_gate": {"passed": False, "errors": ["最终 Markdown 报告内容不完整。"]},
            },
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)
    with TestClient(app) as client:
        created = client.post("/api/analysis-tasks", json={"query": "不要生成占位报告", "mode": "quick"})
        task_key = created.json()["task_key"]
        detail = client.get(f"/api/analysis-tasks/{task_key}")
        report = client.get(f"/api/analysis-tasks/{task_key}/report")

    assert detail.json()["status"] == "failed"
    assert "工作流阶段失败：投研总监" in detail.json()["error_message"]
    assert detail.json()["report_path"] == ""
    assert report.status_code == 404


def test_analysis_task_templates_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/analysis-tasks/templates")

    assert response.status_code == 200
    items = response.json()["items"]
    standard = next(item for item in items if item["key"] == "standard")
    deep = next(item for item in items if item["key"] == "deep")
    assert standard["group"] == "stock"
    assert "TradingAgents" in standard["reference"]
    assert "标准个股投研" in standard["name"]
    assert "流程：" in standard["default_prompt"]
    assert deep["include_report"] is True
    assert "bull" in deep["agent_keys"]
    assert "bear" in deep["agent_keys"]


def test_analysis_task_requires_user_requirement() -> None:
    with TestClient(app) as client:
        response = client.post("/api/analysis-tasks", json={"mode": "standard", "query": "  "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Analysis requirement is required."


def test_analysis_task_template_override_and_defaults(monkeypatch) -> None:
    custom_prompt = "自定义标准投研提示词 pytest"
    captured_variables: dict[str, str] = {}

    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        captured_variables.update(payload.variables)
        return AgentRunRead(
            id=44,
            run_key="AR-TEMPLATE",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=904,
            agent_keys=payload.agent_keys,
            steps=[],
            result={"query": payload.query, "agent_keys": payload.agent_keys},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)

    with TestClient(app) as client:
        updated = client.patch(
            "/api/analysis-tasks/templates/standard",
            json={"default_prompt": custom_prompt},
        )
        listed = client.get("/api/analysis-tasks/templates")
        created = client.post(
            "/api/analysis-tasks",
            json={
                "symbol": "300750",
                "mode": "standard",
                "query": "请分析宁德时代近期风险",
                "agent_keys": ["technical"],
                "variables": {"workflow_instruction": "伪造的前端流程"},
            },
        )
        task_key = created.json()["task_key"]
        detail = client.get(f"/api/analysis-tasks/{task_key}")
        reset = client.delete("/api/analysis-tasks/templates/standard")

    assert updated.status_code == 200
    assert updated.json()["default_prompt"] == custom_prompt
    assert updated.json()["is_customized"] is True
    assert any(
        item["key"] == "standard" and item["default_prompt"] == custom_prompt and item["is_customized"]
        for item in listed.json()["items"]
    )
    assert created.status_code == 200
    assert detail.json()["query"] == "请分析宁德时代近期风险"
    assert "research_director" in detail.json()["agent_keys"]
    assert detail.json()["agent_keys"] != ["technical"]
    assert captured_variables["workflow_instruction"] == custom_prompt
    assert reset.status_code == 200
    assert reset.json()["is_customized"] is False
    assert reset.json()["default_prompt"] != custom_prompt


def test_analysis_task_inline_worker(monkeypatch, tmp_path) -> None:
    report_path = tmp_path / "inline-report.md"
    report_path.write_text("# Inline\n", encoding="utf-8")

    def fake_create_agent_run(db, payload, **kwargs) -> AgentRunRead:
        return AgentRunRead(
            id=43,
            run_key="AR-INLINE",
            symbol=payload.symbol,
            query=payload.query,
            mode=payload.mode,
            status="completed",
            snapshot_id=903,
            agent_keys=payload.agent_keys,
            steps=[
                {
                    "agent_key": "research_director",
                    "agent_name": "投研总监",
                    "tool_key": "document.write",
                    "status": "success",
                    "params": {},
                    "output_preview": {"path": str(report_path)},
                    "error": "",
                }
            ],
            result=valid_pipeline_result("Inline"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr("app.services.analysis_tasks.create_agent_run", fake_create_agent_run)

    with TestClient(app) as client:
        created = client.post(
            "/api/analysis-tasks",
            json={"symbol": "300750", "query": "inline", "agent_keys": ["research_director"]},
        )
        task_key = created.json()["task_key"]

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        result = run_analysis_task_inline(
            db,
            task_key,
            AnalysisTaskCreateRequest(symbol="300750", query="inline", agent_keys=["research_director"]),
        )

    assert result.status == "completed"
    assert result.run_key == "AR-INLINE"


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

        current_version = rollback.json()["current_version"]
        stale_version = updated.json()["current_version"]
        cannot_delete_current = client.delete(f"/api/agents/technical/versions/{current_version}")
        deleted = client.delete(f"/api/agents/technical/versions/{stale_version}")
        remaining_versions = client.get("/api/agents/technical/versions")

    assert cannot_delete_current.status_code == 400
    assert deleted.status_code == 200
    assert deleted.json()["version"] == stale_version
    assert all(item["version"] != stale_version for item in remaining_versions.json()["items"])


def test_agent_skill_crud_and_assignment_context() -> None:
    payload = {
        "key": "test.evidence.skill",
        "name": "测试证据 Skill",
        "description": "验证 Skill 管理接口。",
        "instruction": "仅依据工具结果给出结论。",
        "enabled": True,
        "agent_keys": ["technical"],
    }
    with TestClient(app) as client:
        created = client.post("/api/agent-skills", json=payload)
        listed = client.get("/api/agent-skills")
        with SessionLocal() as db:
            injected = assigned_skill_instructions(db, "technical")
        updated = client.patch(
            "/api/agent-skills/test.evidence.skill",
            json={"enabled": False, "agent_keys": ["fundamental"]},
        )
        deleted = client.delete("/api/agent-skills/test.evidence.skill")

    assert created.status_code == 200
    assert "test.evidence.skill" in {item["key"] for item in listed.json()["items"]}
    assert "仅依据工具结果给出结论。" in injected
    assert updated.status_code == 200
    assert updated.json()["agent_keys"] == ["fundamental"]
    assert deleted.status_code == 204
    with SessionLocal() as db:
        assert "仅依据工具结果给出结论。" not in assigned_skill_instructions(db, "fundamental")


def test_agent_progressively_loads_authorized_skill(monkeypatch) -> None:
    monkeypatch.setattr("app.services.agent_orchestrator.settings.llm_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.agent_orchestrator.execute_tool",
        lambda db, tool_key, params: {"symbol": params["symbol"], "price": 90.0},
    )

    def fake_agent_turn(_db, _model, messages, tools, temperature):
        tool_messages = [item for item in messages if item["role"] == "tool"]
        assert "skill__load" in {item["function"]["name"] for item in tools}
        if not tool_messages:
            assert "A股技术面与量价结构" in messages[0]["content"]
            assert "主板涨跌停通常为 10%" not in messages[0]["content"]
            return {"tool_calls": [{"id": "skill-call", "function": {"name": "skill__load", "arguments": '{"skill_key":"a_share_technical_tape"}'}}]}
        if len(tool_messages) == 1:
            assert "主板涨跌停通常为 10%" in tool_messages[0]["content"]
            return {"tool_calls": [{"id": "quote-call", "function": {"name": "tool__stock_quote", "arguments": '{"symbol":"002594"}'}}]}
        return {"content": json.dumps({
            "summary": "按需加载技术 Skill 后完成分析。",
            "findings": ["价格证据已获取"],
            "evidence": ["stock.quote 返回 90.0"],
            "risks": [],
            "open_questions": [],
        }, ensure_ascii=False)}

    monkeypatch.setattr("app.services.agent_orchestrator._request_agent_turn", fake_agent_turn)
    with TestClient(app) as client:
        before = next(item for item in client.get("/api/agent-skills").json()["items"] if item["key"] == "a_share_technical_tape")["usage_count"]
        client.patch("/api/agents/technical", json={"tools": ["stock.quote"], "change_note": "progressive skill test"})
        run = client.post("/api/agent-runs", json={"query": "分析比亚迪技术面", "agent_keys": ["technical"]})
        after = next(item for item in client.get("/api/agent-skills").json()["items"] if item["key"] == "a_share_technical_tape")["usage_count"]

    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert [step["tool_key"] for step in run.json()["steps"]] == ["skill.load", "stock.quote"]
    assert after == before + 1

    with SessionLocal() as db:
        assert [item["key"] for item in assigned_skill_catalog(db, "research_director")] == ["investment_committee_synthesis"]
        with pytest.raises(ValueError, match="未启用或未授权"):
            load_assigned_skill(db, "research_director", "a_share_technical_tape")


def test_model_config_supports_chat_embedding_and_rerank() -> None:
    payload = {
        "key": "test.rerank",
        "name": "测试重排模型",
        "capability": "rerank",
        "model": "bge-reranker-v2-m3",
        "base_url": "https://rerank.example.com/v1",
        "api_key": "test-rerank-key",
        "timeout_seconds": 20,
        "enabled": True,
        "is_default": True,
    }
    with TestClient(app) as client:
        listed = client.get("/api/model-configs")
        created = client.post("/api/model-configs", json=payload)
        updated = client.patch("/api/model-configs/test.rerank", json={"model": "bge-reranker-v2-gemma", "enabled": False})
        deleted = client.delete("/api/model-configs/test.rerank")

    capabilities = {item["capability"] for item in listed.json()["items"]}
    assert {"chat", "embedding"}.issubset(capabilities)
    assert created.status_code == 200
    assert created.json()["api_key_configured"] is True
    assert "test-rerank-key" not in created.json()["api_key_masked"]
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert deleted.status_code == 204


def test_single_agent_chat_uses_agent_tools(monkeypatch) -> None:
    def fake_execute_tool(db, tool_key, params):
        return {"symbol": params.get("symbol"), "items": [{"title": "测试上下文"}]}

    monkeypatch.setattr("app.services.agent_chat.execute_tool", fake_execute_tool)
    monkeypatch.setattr("app.services.agent_chat.settings.llm_api_key", "test-key")

    def fake_chat_turn(_db, _model, messages, tools, temperature):
        assert any(item["function"]["name"] == "tool__stock_quote" for item in tools)
        if any(item["role"] == "tool" for item in messages):
            assert "测试上下文" in messages[-1]["content"]
            return {"content": "工具结果已用于技术面判断。"}
        return {
            "tool_calls": [
                {"id": "chat-call-1", "function": {"name": "tool__stock_quote", "arguments": '{"symbol":"300750"}'}}
            ]
        }

    monkeypatch.setattr("app.services.agent_chat._request_chat_turn", fake_chat_turn)

    with TestClient(app) as client:
        client.patch(
            "/api/agents/technical",
            json={"tools": ["stock.quote", "stock.indicators"], "change_note": "chat tool test"},
        )
        response = client.post(
            "/api/agent-chat/technical",
            json={"message": "300750 技术面怎么看", "symbol": "300750"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_key"] == "technical"
    assert body["model_status"] == "llm_completed"
    assert body["tool_calls"]
    assert body["tool_calls"][0]["tool_key"] == "stock.quote"
    assert "技术面" in body["content"]


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


def test_stock_tool_function_schemas_require_symbol() -> None:
    """The LLM receives these schemas directly, so required handler inputs must be explicit."""
    from app.services.agent_tools import TOOL_REGISTRY

    symbol_tools = {
        "stock.quote",
        "stock.bars",
        "stock.indicators",
        "stock.news",
        "stock.announcements",
        "stock.research_reports",
        "stock.fundamentals",
        "stock.financial_statements",
        "stock.fund_flow",
        "stock.dragon_tiger",
        "stock.margin_trading",
        "stock.lockup_expiry",
    }
    for tool_key in symbol_tools:
        schema = TOOL_REGISTRY[tool_key].input_schema
        assert "symbol" in schema.get("required", [])
        assert "symbol" in schema.get("properties", {})


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


def test_finance_and_general_web_search_tools(monkeypatch) -> None:
    class FakeSearchResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "code": 200,
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "比亚迪股份有限公司公告",
                                "url": "https://www.cninfo.com.cn/new/disclosure/detail?stockCode=002594",
                                "summary": "比亚迪发布最新经营公告。",
                                "datePublished": "2026-07-12",
                            }
                        ]
                    }
                },
            }

    monkeypatch.setattr("app.services.web_search.httpx.post", lambda *args, **kwargs: FakeSearchResponse())

    with TestClient(app) as client:
        credential = client.post(
            "/api/data/providers/bocha_search/credentials",
            json={"credential_type": "api_key", "value": "pytest-key"},
        )
        client.patch(
            "/api/agents/news",
            json={"tools": ["finance.search", "web.search"], "change_note": "search tool test"},
        )
        finance = client.post(
            "/api/agent-tools/news/finance.search/run",
            json={"params": {"query": "比亚迪最新公告", "symbol": "002594", "limit": 5}},
        )
        general = client.post(
            "/api/agent-tools/news/web.search/run",
            json={"params": {"query": "新能源汽车产业", "limit": 5}},
        )

    assert credential.status_code == 200
    assert finance.status_code == 200
    assert finance.json()["output"]["provider_key"] == "bocha_search"
    assert finance.json()["output"]["items"][0]["source_type"] == "official_disclosure"
    assert finance.json()["output"]["items"][0]["authority_level"] == 5
    assert general.status_code == 200
    assert general.json()["output"]["search_type"] == "web"


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
    monkeypatch.setattr("app.services.agent_orchestrator.settings.llm_api_key", "test-key")

    def fake_agent_turn(_db, _model, messages, tools, temperature):
        names = {item["function"]["name"] for item in tools}
        assert names == {"tool__stock_quote", "tool__stock_indicators", "skill__load"}
        first_turn = not any(item["role"] == "tool" for item in messages)
        if first_turn:
            context = json.loads(messages[1]["content"])
            assert context["user_requirement"] == "测试技术面工具编排"
            assert "workflow_instruction" not in context
            assert "任务工作流约束：内部技术面工作流" in messages[0]["content"]
            assert "当前步骤目标：" in messages[0]["content"]
        if any(item["role"] == "tool" for item in messages):
            assert "300.5" in messages[-2]["content"]
            return {"content": json.dumps({
                "summary": "技术面工具调用完成。",
                "findings": ["价格与指标数据已返回"],
                "evidence": ["stock.quote 与 stock.indicators 工具结果"],
                "risks": [],
                "open_questions": [],
            }, ensure_ascii=False)}
        return {
            "tool_calls": [
                {"id": "run-call-1", "function": {"name": "tool__stock_quote", "arguments": '{"symbol":"300750"}'}},
                {"id": "run-call-2", "function": {"name": "tool__stock_indicators", "arguments": '{"symbol":"300750","period":"daily"}'}},
            ]
        }

    monkeypatch.setattr("app.services.agent_orchestrator._request_agent_turn", fake_agent_turn)

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
                "variables": {"workflow_instruction": "内部技术面工作流"},
            },
        )

        assert created.status_code == 200
        body = created.json()
        run_key = body["run_key"]
        listed = client.get("/api/agent-runs")
        fetched = client.get(f"/api/agent-runs/{run_key}")

    assert body["status"] == "completed"
    assert body["symbol"] == "300750"
    assert body["snapshot_id"] == 0
    assert body["result"]["snapshot_id"] == 0
    assert body["agent_keys"] == ["technical"]
    assert [step["tool_key"] for step in body["steps"]] == ["stock.quote", "stock.indicators"]
    assert body["result"]["tool_success_count"] == 2
    assert body["result"]["agent_summaries"][0]["artifact"]["summary"] == "技术面工具调用完成。"
    assert listed.status_code == 200
    assert any(item["run_key"] == run_key for item in listed.json()["items"])
    assert fetched.status_code == 200
    assert fetched.json()["run_key"] == run_key


def test_agent_run_emits_auditable_context(monkeypatch) -> None:
    from app.schemas.agent_run import AgentRunCreateRequest
    from app.services.agent_orchestrator import create_agent_run

    monkeypatch.setattr("app.services.agent_orchestrator.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.services.agent_orchestrator.execute_tool", lambda db, tool_key, params: {"symbol": params["symbol"]})

    def fake_agent_turn(_db, _model, messages, tools, temperature):
        if any(item["role"] == "tool" for item in messages):
            return {"content": json.dumps({
                "summary": "已完成。",
                "findings": ["已获得行情证据"],
                "evidence": ["stock.quote 工具结果"],
                "risks": [],
                "open_questions": [],
            }, ensure_ascii=False)}
        return {"tool_calls": [{"id": "context-call", "function": {"name": "tool__stock_quote", "arguments": '{"symbol":"300750"}'}}]}

    monkeypatch.setattr("app.services.agent_orchestrator._request_agent_turn", fake_agent_turn)
    events: list[dict] = []

    with TestClient(app) as client:
        client.patch("/api/agents/technical", json={"tools": ["stock.quote"], "change_note": "context audit"})
        with SessionLocal() as db:
            create_agent_run(
                db,
                AgentRunCreateRequest(
                    symbol="300750",
                    query="验证近期趋势是否可靠",
                    agent_keys=["technical"],
                    variables={"workflow_instruction": "技术面流程约束"},
                ),
                on_event=events.append,
            )

    context = next(event for event in events if event["event_type"] == "agent_context")
    assert context["payload"]["user_requirement"] == "验证近期趋势是否可靠"
    assert context["payload"]["current_step_goal"]
    assert "技术面流程约束" in context["payload"]["system_prompt"]
    assert context["payload"]["allowed_tools"] == ["stock.quote", "skill.load"]
    assert context["payload"]["available_skills"]


def test_agent_run_uses_llm_result_when_configured(monkeypatch) -> None:
    def fake_execute_tool(db, tool_key: str, params: dict) -> dict:
        return {"symbol": params["symbol"], "price": 300.5, "provider_key": "pytest"}

    monkeypatch.setattr("app.services.agent_orchestrator.execute_tool", fake_execute_tool)
    monkeypatch.setattr("app.services.agent_orchestrator.settings.llm_api_key", "test-key")

    def fake_agent_turn(_db, _model, messages, tools, temperature):
        if "最终汇总 Agent" in messages[0]["content"]:
            report = valid_pipeline_result("模型生成的最终报告")
            return {"content": json.dumps({
                "title": report["title"],
                "executive_summary": report["summary"],
                "conclusion": "模型结论：谨慎观察",
                "horizon": "daily",
                "confidence": 68,
                "key_evidence": ["行情工具已返回"],
                "risks": ["外部测试风险"],
                "watch_items": ["成交量"],
                "markdown_report": report["markdown_report"],
            }, ensure_ascii=False)}
        if any(item["role"] == "tool" for item in messages):
            return {"content": json.dumps({
                "summary": "行情工具调用完成。",
                "findings": ["最新价格为 300.5"],
                "evidence": ["stock.quote 返回 300.5"],
                "risks": [],
                "open_questions": [],
            }, ensure_ascii=False)}
        return {
            "tool_calls": [
                {"id": "llm-call-1", "function": {"name": "tool__stock_quote", "arguments": '{"symbol":"300750"}'}}
            ]
        }

    monkeypatch.setattr("app.services.agent_orchestrator._request_agent_turn", fake_agent_turn)

    with TestClient(app) as client:
        client.patch(
            "/api/agents/data_steward",
            json={"tools": ["stock.quote"], "change_note": "llm orchestration test"},
        )
        client.patch(
            "/api/agents/research_director",
            json={"tools": [], "change_note": "final synthesis without direct tools"},
        )
        created = client.post(
            "/api/agent-runs",
            json={
                "symbol": "300750",
                "query": "测试模型总结",
                "agent_keys": ["data_steward", "research_director"],
            },
        )

    assert created.status_code == 200
    result = created.json()["result"]
    assert created.json()["snapshot_id"] == 0
    assert result["conclusion"] == "模型结论：谨慎观察"
    assert result["model_status"] == "agent_pipeline"
    assert result["quality_gate"]["passed"] is True
    assert result["confidence"] == 68

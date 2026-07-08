from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentConfig, AgentRun
from app.schemas.agent_run import AgentRunCreateRequest, AgentRunRead, AgentRunStep
from app.services.agent_tools import AgentToolError, execute_tool, get_tool_spec
from app.services.llm_client import generate_run_conclusion
from app.services.stock_catalog import get_stock_profile


DEFAULT_AGENT_PIPELINE = [
    "data_steward",
    "technical",
    "news",
    "fundamental",
    "policy_industry",
    "capital_flow",
    "risk",
    "research_director",
]


def create_agent_run(db: Session, payload: AgentRunCreateRequest) -> AgentRunRead:
    symbol = _normalize_symbol(payload.symbol)
    agents = _select_agents(db, payload.agent_keys)
    run_key = f"AR-{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    steps: list[AgentRunStep] = []
    agent_summaries: list[dict[str, Any]] = []
    variables = _build_variables(symbol, payload)

    for agent in agents:
        agent_steps: list[AgentRunStep] = []
        for tool_key in _agent_tools(agent):
            if tool_key == "knowledge.search":
                continue
            if tool_key == "document.write" and not payload.include_report:
                continue
            params = _tool_params(tool_key, symbol, payload, agent_summaries)
            if params is None:
                continue
            try:
                output = execute_tool(db, tool_key, params)
                step = AgentRunStep(
                    agent_key=agent.key,
                    agent_name=agent.name,
                    tool_key=tool_key,
                    status="success",
                    params=params,
                    output_preview=_preview_output(output),
                )
            except AgentToolError as exc:
                step = AgentRunStep(
                    agent_key=agent.key,
                    agent_name=agent.name,
                    tool_key=tool_key,
                    status="failed",
                    params=params,
                    error=str(exc),
                )
            agent_steps.append(step)
            steps.append(step)
        agent_summaries.append(_agent_summary(agent, agent_steps, variables))

    status = "completed" if steps and all(step.status == "success" for step in steps) else "partial"
    if not steps:
        status = "no_tools"
    result = _build_result(symbol, payload, agent_summaries, steps)
    run = AgentRun(
        run_key=run_key,
        symbol=symbol,
        query=payload.query,
        mode=payload.mode,
        status=status,
        agent_keys_json=json.dumps([agent.key for agent in agents], ensure_ascii=False),
        steps_json=json.dumps([step.model_dump(mode="json") for step in steps], ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return agent_run_read(run)


def agent_run_read(run: AgentRun) -> AgentRunRead:
    return AgentRunRead(
        id=run.id,
        run_key=run.run_key,
        symbol=run.symbol,
        query=run.query,
        mode=run.mode,
        status=run.status,
        agent_keys=_json_list(run.agent_keys_json),
        steps=[AgentRunStep(**item) for item in _json_list_of_dict(run.steps_json)],
        result=_json_dict(run.result_json),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _select_agents(db: Session, agent_keys: list[str]) -> list[AgentConfig]:
    requested = agent_keys or DEFAULT_AGENT_PIPELINE
    rows = db.scalars(select(AgentConfig).where(AgentConfig.key.in_(requested))).all()
    by_key = {agent.key: agent for agent in rows if agent.enabled}
    return [by_key[key] for key in requested if key in by_key]


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")


def _agent_tools(agent: AgentConfig) -> list[str]:
    return _json_list(agent.tools_json)


def _build_variables(symbol: str, payload: AgentRunCreateRequest) -> dict[str, str]:
    profile = get_stock_profile(symbol)
    values = {
        "stock_code": symbol,
        "stock_name": profile.name if profile else symbol,
        "period": payload.period,
        "query": payload.query,
    }
    values.update(payload.variables)
    return values


def _tool_params(
    tool_key: str,
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        spec = get_tool_spec(tool_key)
    except AgentToolError:
        return None
    if not spec.enabled:
        return None
    if tool_key in {"stock.quote", "stock.fundamentals"}:
        return {"symbol": symbol}
    if tool_key in {
        "stock.news",
        "stock.announcements",
        "stock.research_reports",
        "stock.fund_flow",
        "stock.dragon_tiger",
        "stock.lockup_expiry",
        "stock.margin_trading",
    }:
        return {"symbol": symbol, "limit": min(payload.limit, 50)}
    if tool_key == "stock.bars":
        return {"symbol": symbol, "period": payload.period, "limit": payload.limit}
    if tool_key == "stock.indicators":
        return {
            "symbol": symbol,
            "period": payload.period,
            "limit": payload.limit,
            "names": ["ma", "macd", "rsi", "kdj", "boll"],
        }
    if tool_key == "stock.financial_statements":
        return {"symbol": symbol, "statement_type": "income", "limit": 4}
    if tool_key == "market.northbound_flow":
        return {"limit": min(payload.limit, 50)}
    if tool_key == "sector.snapshots":
        return {"sector_type": "industry", "limit": 20}
    if tool_key == "market.macro":
        return {"indicator": "cpi", "limit": 12}
    if tool_key == "data.quality":
        return {"log_limit": 500}
    if tool_key == "document.write":
        return _document_params(symbol, payload, agent_summaries)
    return None


def _document_params(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    sections = [
        {
            "heading": item["agent_name"],
            "bullets": item["bullets"] or ["无可用工具结果"],
        }
        for item in agent_summaries
    ]
    return {
        "title": f"{symbol} Agent 分析报告",
        "topic": symbol,
        "summary": payload.query or "自动生成的 Agent 工具编排报告。",
        "sections": sections,
        "references": [item["tool_key"] for item in _flatten_tool_summaries(agent_summaries)],
    }


def _agent_summary(agent: AgentConfig, steps: list[AgentRunStep], variables: dict[str, str]) -> dict[str, Any]:
    success = [step for step in steps if step.status == "success"]
    failed = [step for step in steps if step.status != "success"]
    bullets = []
    for step in success:
        bullets.append(f"{step.tool_key}: {step.output_preview.get('summary', '已获取数据')}")
    for step in failed:
        bullets.append(f"{step.tool_key}: 失败，{step.error}")
    return {
        "agent_key": agent.key,
        "agent_name": agent.name,
        "role": agent.role,
        "status": "success" if success and not failed else "partial" if success else "failed",
        "tool_count": len(steps),
        "success_count": len(success),
        "bullets": bullets,
        "prompt_variables": {key: variables[key] for key in sorted(variables)},
    }


def _build_result(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
    steps: list[AgentRunStep],
) -> dict[str, Any]:
    result = generate_run_conclusion(symbol, payload, agent_summaries, steps)
    result["references"] = [
        {
            "agent_key": step.agent_key,
            "tool_key": step.tool_key,
            "status": step.status,
        }
        for step in steps
    ]
    return result


def _preview_output(output: dict[str, Any]) -> dict[str, Any]:
    if "items" in output and isinstance(output["items"], list):
        return {"summary": f"{len(output['items'])} items", "sample": output["items"][:2]}
    if "metrics" in output and isinstance(output["metrics"], list):
        return {"summary": f"{len(output['metrics'])} metrics", "sample": output["metrics"][:3]}
    if "content" in output:
        text = str(output["content"])
        return {"summary": f"document {len(text)} chars", "path": output.get("path", "")}
    keys = sorted(output.keys())
    return {"summary": f"{len(keys)} fields", "fields": keys[:12]}


def _flatten_tool_summaries(agent_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in agent_summaries:
        for bullet in item.get("bullets", []):
            match = re.match(r"([^:]+):", bullet)
            if match:
                rows.append({"tool_key": match.group(1)})
    return rows


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_list_of_dict(value: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

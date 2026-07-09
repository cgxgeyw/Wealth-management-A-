from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentConfig
from app.schemas.agent_chat import AgentChatRequest, AgentChatResponse, AgentChatToolCall
from app.services.agent_tools import AgentToolError, execute_tool, get_tool_spec
from app.services.stock_catalog import get_stock_profile


def create_agent_chat_response(db: Session, agent_key: str, payload: AgentChatRequest) -> AgentChatResponse:
    agent = db.scalar(select(AgentConfig).where(AgentConfig.key == agent_key))
    if not agent or not agent.enabled:
        raise AgentToolError("Agent not found.", status_code=404)
    symbol = _resolve_symbol(payload)
    variables = _build_variables(symbol, payload)
    tool_calls = _run_context_tools(db, agent, symbol, payload)
    fallback = _fallback_reply(agent, payload, symbol, tool_calls)
    model_status = "fallback_no_api_key"
    model = ""
    content = fallback
    if settings.llm_api_key:
        try:
            content = _call_llm(agent, payload, variables, tool_calls)
            model_status = "llm_completed"
            model = settings.llm_model
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            content = f"{fallback}\n\n模型调用失败：{exc}"
            model_status = "fallback_llm_error"
            model = settings.llm_model
    return AgentChatResponse(
        agent_key=agent.key,
        agent_name=agent.name,
        content=content,
        model_status=model_status,
        model=model,
        tool_calls=tool_calls,
        created_at=datetime.now(ZoneInfo("Asia/Shanghai")),
    )


def _run_context_tools(db: Session, agent: AgentConfig, symbol: str, payload: AgentChatRequest) -> list[AgentChatToolCall]:
    tool_keys = _json_list(agent.tools_json)
    selected = _select_tools(tool_keys, payload.message, payload.max_tool_calls)
    calls: list[AgentChatToolCall] = []
    for tool_key in selected:
        params = _tool_params(tool_key, symbol, payload)
        if params is None:
            continue
        try:
            output = execute_tool(db, tool_key, params)
            calls.append(
                AgentChatToolCall(
                    tool_key=tool_key,
                    status="success",
                    params=params,
                    output_preview=_preview_output(output),
                )
            )
        except AgentToolError as exc:
            calls.append(AgentChatToolCall(tool_key=tool_key, status="failed", params=params, error=str(exc)))
    return calls


def _select_tools(tool_keys: list[str], message: str, limit: int) -> list[str]:
    if limit <= 0:
        return []
    lower = message.lower()
    priorities: list[str] = []
    keyword_map = [
        ("stock.indicators", ["技术", "指标", "macd", "kdj", "rsi", "boll", "均线"]),
        ("stock.bars", ["k线", "走势", "趋势", "支撑", "压力", "量价"]),
        ("stock.news", ["新闻", "消息", "事件", "舆情"]),
        ("stock.announcements", ["公告", "披露"]),
        ("stock.research_reports", ["研报", "评级"]),
        ("stock.fundamentals", ["基本面", "估值", "pe", "pb", "roe", "利润"]),
        ("stock.financial_statements", ["财报", "利润表", "资产负债", "现金流"]),
        ("stock.fund_flow", ["资金", "主力", "流入", "流出"]),
        ("stock.dragon_tiger", ["龙虎榜", "游资"]),
        ("stock.margin_trading", ["融资", "融券", "两融"]),
        ("stock.lockup_expiry", ["解禁", "减持"]),
        ("market.macro", ["宏观", "cpi", "pmi"]),
        ("sector.snapshots", ["行业", "板块", "概念"]),
        ("knowledge.search", ["知识库", "资料", "规则", "策略"]),
    ]
    for tool_key, keywords in keyword_map:
        if tool_key in tool_keys and any(keyword in lower or keyword in message for keyword in keywords):
            priorities.append(tool_key)
    if "stock.quote" in tool_keys:
        priorities.insert(0, "stock.quote")
    for tool_key in tool_keys:
        if tool_key not in priorities and tool_key != "document.write":
            priorities.append(tool_key)
    return priorities[:limit]


def _tool_params(tool_key: str, symbol: str, payload: AgentChatRequest) -> dict[str, Any] | None:
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
        return {"symbol": symbol, "limit": 20}
    if tool_key == "stock.bars":
        return {"symbol": symbol, "period": payload.variables.get("period", "daily"), "limit": 80}
    if tool_key == "stock.indicators":
        return {"symbol": symbol, "period": payload.variables.get("period", "daily"), "limit": 80}
    if tool_key == "stock.financial_statements":
        return {"symbol": symbol, "statement_type": "income", "limit": 4}
    if tool_key == "knowledge.search":
        return {"query": payload.message, "symbols": [symbol], "top_k": 5, "require_citations": True}
    if tool_key == "market.northbound_flow":
        return {"limit": 20}
    if tool_key == "sector.snapshots":
        return {"sector_type": "industry", "limit": 10}
    if tool_key == "market.macro":
        return {"indicator": "cpi", "limit": 6}
    if tool_key == "data.quality":
        return {"log_limit": 200}
    return None


def _call_llm(
    agent: AgentConfig,
    payload: AgentChatRequest,
    variables: dict[str, str],
    tool_calls: list[AgentChatToolCall],
) -> str:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                _render(agent.system_prompt, variables)
                + "\n你正在进行单 Agent 对话。不要输出固定报告 JSON。"
                + "可以自然追问，但涉及行情、新闻、财务时必须说明依据来自工具结果。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task_prompt": _render(agent.task_prompt, variables),
                    "tool_context": [call.model_dump(mode="json") for call in tool_calls],
                    "question": payload.message,
                },
                ensure_ascii=False,
            ),
        },
    ]
    for item in payload.history[-8:]:
        if item.role in {"user", "assistant"}:
            messages.insert(-1, {"role": item.role, "content": item.content})
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
            json={"model": settings.llm_model, "messages": messages, "temperature": agent.temperature},
        )
        response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"])


def _fallback_reply(
    agent: AgentConfig,
    payload: AgentChatRequest,
    symbol: str,
    tool_calls: list[AgentChatToolCall],
) -> str:
    success = [call for call in tool_calls if call.status == "success"]
    failed = [call for call in tool_calls if call.status != "success"]
    lines = [
        f"我是{agent.name} Agent。当前没有配置可用模型，所以先按工具结果给你一个简短回应。",
        f"问题：{payload.message}",
    ]
    if symbol:
        lines.append(f"标的：{symbol}")
    if success:
        lines.append("已读取：" + "、".join(call.tool_key for call in success))
        for call in success[:3]:
            lines.append(f"- {call.tool_key}: {call.output_preview.get('summary', '已获取上下文')}")
    else:
        lines.append("这次没有拿到可用工具结果，我需要更多上下文或可用数据源。")
    if failed:
        lines.append("失败工具：" + "、".join(f"{call.tool_key}({call.error})" for call in failed[:3]))
    lines.append("你可以继续追问具体点，例如只问技术面、新闻影响、资金流或风险条件。")
    return "\n".join(lines)


def _build_variables(symbol: str, payload: AgentChatRequest) -> dict[str, str]:
    profile = get_stock_profile(symbol)
    values = {
        "stock_code": symbol,
        "stock_name": profile.name if profile else symbol,
        "period": payload.variables.get("period", "daily"),
        "query": payload.message,
    }
    values.update(payload.variables)
    return values


def _render(template: str, variables: dict[str, str]) -> str:
    result = template
    for key, value in variables.items():
        result = re.sub(r"{{\s*" + re.escape(key) + r"\s*}}", value, result)
    return result


def _resolve_symbol(payload: AgentChatRequest) -> str:
    if payload.symbol.strip():
        return _normalize_symbol(payload.symbol)
    match = re.search(r"\b(?:sh|sz|bj)?(\d{6})\b", payload.message, re.IGNORECASE)
    return _normalize_symbol(match.group(1)) if match else ""


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")


def _preview_output(output: dict[str, Any]) -> dict[str, Any]:
    if "items" in output and isinstance(output["items"], list):
        return {"summary": f"{len(output['items'])} items", "sample": output["items"][:2]}
    if "metrics" in output and isinstance(output["metrics"], list):
        return {"summary": f"{len(output['metrics'])} metrics", "sample": output["metrics"][:3]}
    keys = sorted(output.keys())
    return {"summary": f"{len(keys)} fields", "fields": keys[:10]}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []

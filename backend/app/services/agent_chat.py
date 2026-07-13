from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.agent_audit import AgentChatTrace, AgentToolCallAudit
from app.schemas.agent_chat import AgentChatKnowledgeHit, AgentChatRequest, AgentChatResponse, AgentChatToolCall
from app.services.agent_tools import AgentToolError, execute_tool, get_tool_spec
from app.services.agent_skills import assigned_skill_catalog, load_assigned_skill
from app.services.model_runtime import get_model_runtime
from app.services.stock_catalog import get_stock_profile


def create_agent_chat_response(db: Session, agent_key: str, payload: AgentChatRequest) -> AgentChatResponse:
    agent = db.scalar(select(AgentConfig).where(AgentConfig.key == agent_key))
    if not agent or not agent.enabled:
        raise AgentToolError("Agent not found.", status_code=404)
    symbol = _resolve_symbol(payload)
    variables = _build_variables(symbol, payload)
    tool_calls: list[AgentChatToolCall] = []
    knowledge_hits: list[AgentChatKnowledgeHit] = []
    conversation_id = payload.conversation_id.strip() or f"conv_{uuid4().hex}"
    turn_id = f"turn_{uuid4().hex}"
    fallback = _fallback_reply(agent, payload, symbol, tool_calls)
    model_status = "fallback_no_api_key"
    model = ""
    content = fallback
    runtime = get_model_runtime(db, "chat", agent.model)
    sequence = 1
    _record_trace(
        db, conversation_id, turn_id, agent.key, sequence, "turn_started", "info", runtime.model,
        {"max_tool_calls": payload.max_tool_calls, "history_count": len(payload.history)},
    )
    if runtime.api_key:
        try:
            content, tool_calls, sequence = _run_agent_tool_loop(
                db, agent, payload, variables, conversation_id, turn_id, sequence,
            )
            fallback = _fallback_reply(agent, payload, symbol, tool_calls)
            content = content or fallback
            model_status = "llm_completed"
            model = runtime.model
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as exc:
            content = f"{fallback}\n\n模型调用失败：{exc}"
            model_status = "fallback_llm_error"
            model = runtime.model
            _record_trace(db, conversation_id, turn_id, agent.key, sequence + 1, "model_error", "failed", model, {}, str(exc))
    else:
        _record_trace(db, conversation_id, turn_id, agent.key, sequence + 1, "model_unavailable", "failed", runtime.model, {}, "No API key available")
    _record_trace(
        db, conversation_id, turn_id, agent.key, sequence + 2, "turn_completed", model_status,
        model, {"tool_call_count": len(tool_calls), "content_length": len(content)},
    )
    return AgentChatResponse(
        conversation_id=conversation_id,
        turn_id=turn_id,
        agent_key=agent.key,
        agent_name=agent.name,
        content=content,
        model_status=model_status,
        model=model,
        tool_calls=tool_calls,
        knowledge_hits=knowledge_hits,
        created_at=datetime.now(ZoneInfo("Asia/Shanghai")),
    )


def _run_agent_tool_loop(
    db: Session,
    agent: AgentConfig,
    payload: AgentChatRequest,
    variables: dict[str, str],
    conversation_id: str,
    turn_id: str,
    sequence: int,
) -> tuple[str, list[AgentChatToolCall], int]:
    skill_catalog = assigned_skill_catalog(db, agent.key)
    allowed = _chat_tool_definitions(agent, skill_catalog)
    tool_by_function = {item["function"]["name"]: item["tool_key"] for item in allowed}
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": _render(agent.system_prompt, variables)
            + ("\n\n可用 Skill 目录：" + json.dumps(skill_catalog, ensure_ascii=False)
               + "。需要时调用 skill__load 获取完整 instruction；未加载的 Skill 不得假装已经遵循。" if skill_catalog else "")
            + "\n根据需要调用工具；没有可靠参数时先追问，不要猜测。",
        },
        {"role": "user", "content": _render(agent.task_prompt, variables) + "\n\n用户问题：" + payload.message},
    ]
    for item in payload.history[-8:]:
        if item.role in {"user", "assistant"}:
            messages.insert(-1, {"role": item.role, "content": item.content})

    calls: list[AgentChatToolCall] = []
    while len(calls) < payload.max_tool_calls:
        sequence += 1
        _record_trace(db, conversation_id, turn_id, agent.key, sequence, "model_request", "running", agent.model, {"round": sequence, "tool_call_count": len(calls)})
        message = _request_chat_turn(db, agent.model, messages, allowed, agent.temperature)
        requested = message.get("tool_calls") or []
        sequence += 1
        _record_trace(db, conversation_id, turn_id, agent.key, sequence, "model_response", "success", agent.model, {"round": sequence - 1, "tool_call_count": len(requested), "content_length": len(str(message.get("content") or ""))})
        if not isinstance(requested, list) or not requested:
            return str(message.get("content") or ""), calls, sequence
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": requested})
        for tool_call in requested[: payload.max_tool_calls - len(calls)]:
            output: dict[str, Any] | None = None
            function = tool_call.get("function") if isinstance(tool_call, dict) else None
            function_name = function.get("name") if isinstance(function, dict) else ""
            tool_key = tool_by_function.get(str(function_name), str(function_name))
            params, parse_error = _tool_call_params(function)
            sequence += 1
            _record_trace(db, conversation_id, turn_id, agent.key, sequence, "tool_started", "running", agent.model, {"tool_key": tool_key, "params": params})
            if function_name not in tool_by_function:
                call = AgentChatToolCall(tool_key=tool_key, status="failed", error="模型请求了未授权工具。")
            elif parse_error:
                call = AgentChatToolCall(tool_key=tool_key, status="failed", error=parse_error)
            else:
                try:
                    if tool_key == "skill.load":
                        output = load_assigned_skill(db, agent.key, str(params.get("skill_key") or ""), "chat")
                    else:
                        output = execute_tool(db, tool_key, params)
                    call = AgentChatToolCall(tool_key=tool_key, status="success", params=params, output_preview=_preview_output(output))
                except (AgentToolError, ValueError) as exc:
                    call = AgentChatToolCall(tool_key=tool_key, status="failed", params=params, error=str(exc))
            calls.append(call)
            db.add(AgentToolCallAudit(agent_key=agent.key, tool_key=tool_key, status=call.status, error=call.error))
            db.commit()
            sequence += 1
            _record_trace(db, conversation_id, turn_id, agent.key, sequence, "tool_completed", call.status, agent.model, {"tool_key": tool_key, "output_preview": call.output_preview}, call.error)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call.get("id") or ""),
                    "content": json.dumps(
                        {"tool_key": tool_key, "status": call.status, "output": output, "error": call.error},
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            )
    sequence += 1
    _record_trace(db, conversation_id, turn_id, agent.key, sequence, "model_request", "running", agent.model, {"round": sequence, "tool_call_count": len(calls), "final_after_tool_limit": True})
    message = _request_chat_turn(db, agent.model, messages, allowed, agent.temperature)
    requested = message.get("tool_calls") or []
    sequence += 1
    if isinstance(requested, list) and requested:
        _record_trace(db, conversation_id, turn_id, agent.key, sequence, "tool_limit_reached", "blocked", agent.model, {"tool_call_count": len(calls), "pending_tool_call_count": len(requested)})
        return "工具调用已达到本轮上限，未执行后续工具请求。请查看该轮执行轨迹后重试。", calls, sequence
    _record_trace(db, conversation_id, turn_id, agent.key, sequence, "model_response", "success", agent.model, {"final_after_tool_limit": True, "content_length": len(str(message.get("content") or ""))})
    return str(message.get("content") or ""), calls, sequence


def _record_trace(
    db: Session,
    conversation_id: str,
    turn_id: str,
    agent_key: str,
    sequence: int,
    event_type: str,
    status: str,
    model: str,
    detail: dict[str, Any],
    error: str = "",
) -> None:
    db.add(AgentChatTrace(
        conversation_id=conversation_id,
        turn_id=turn_id,
        agent_key=agent_key,
        event_type=event_type,
        sequence=sequence,
        status=status,
        model=model,
        detail_json=json.dumps(detail, ensure_ascii=False, default=str),
        error=error,
    ))
    db.commit()


def _chat_tool_definitions(agent: AgentConfig, skill_catalog: list[dict[str, str]]) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for tool_key in _json_list(agent.tools_json):
        try:
            spec = get_tool_spec(tool_key)
        except AgentToolError:
            continue
        if not spec.enabled:
            continue
        definitions.append(
            {
                "type": "function",
                "tool_key": tool_key,
                "function": {
                    "name": "tool__" + tool_key.replace(".", "_").replace("-", "_"),
                    "description": spec.description,
                    "parameters": spec.input_schema or {"type": "object", "properties": {}},
                },
            }
        )
    if skill_catalog:
        definitions.append(
            {
                "type": "function",
                "tool_key": "skill.load",
                "function": {
                    "name": "skill__load",
                    "description": "按需加载一个已授权 Skill 的完整 instruction。",
                    "parameters": {
                        "type": "object",
                        "required": ["skill_key"],
                        "properties": {
                            "skill_key": {
                                "type": "string",
                                "enum": [item["key"] for item in skill_catalog],
                            }
                        },
                    },
                },
            }
        )
    return definitions


def _request_chat_turn(db: Session, preferred_model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: float) -> dict[str, Any]:
    runtime = get_model_runtime(db, "chat", preferred_model)
    with httpx.Client(timeout=runtime.timeout_seconds) as client:
        response = client.post(
            runtime.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {runtime.api_key}", "Content-Type": "application/json"},
            json={
                "model": runtime.model,
                "messages": messages,
                "tools": [{"type": item["type"], "function": item["function"]} for item in tools],
                "tool_choice": "auto",
                "temperature": temperature,
            },
        )
        response.raise_for_status()
    message = response.json()["choices"][0]["message"]
    if not isinstance(message, dict):
        raise ValueError("LLM tool-call response is not an object.")
    return message


def _tool_call_params(function: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(function, dict):
        return {}, "模型返回了无效的工具调用。"
    try:
        params = json.loads(str(function.get("arguments") or "{}"))
    except json.JSONDecodeError:
        return {}, "模型返回的工具参数不是有效 JSON。"
    return (params, "") if isinstance(params, dict) else ({}, "模型返回的工具参数必须是对象。")


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

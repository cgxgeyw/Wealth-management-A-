from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from json_repair import repair_json
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import settings  # noqa: F401 - retained for test/runtime configuration hooks
from app.models.agent import AgentConfig, AgentRun
from app.models.agent_audit import AgentToolCallAudit
from app.schemas.agent_run import AgentRunCreateRequest, AgentRunRead, AgentRunStep
from app.services.agent_tools import AgentToolError, execute_tool, get_tool_spec
from app.services.agent_skills import assigned_skill_catalog, load_assigned_skill
from app.services.model_runtime import get_model_runtime
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

FINAL_AGENT_KEY = "research_director"
SYNTHESIS_AGENT_KEYS = {"bull", "bear", FINAL_AGENT_KEY}


def _output_contract(is_final: bool) -> str:
    if is_final:
        return (
            "你是工作流的最终汇总 Agent。必须综合全部上游阶段产物并直接回答用户需求。"
            "最终响应只能是一个 JSON 对象，不得包含解释、前后缀或 Markdown 代码围栏。严格 Schema："
            '{"title":"string","executive_summary":"string","conclusion":"string","horizon":"string",'
            '"confidence":0,"key_evidence":["string"],"risks":["string"],"watch_items":["string"],'
            '"markdown_report":"string"}。confidence 必须是 0 到 100 的整数；key_evidence、risks、watch_items '
            "必须是字符串数组；markdown_report 必须是完整可读的 Markdown 分析报告字符串，包含结论、依据、"
            "反证或风险、观察条件。JSON 字符串内的换行必须正确转义。禁止输出工具执行计数或占位内容。"
        )
    return (
        "你是工作流的专业分析阶段。最终响应只能是一个 JSON 对象，不得包含解释、前后缀或 Markdown 代码围栏。"
        '严格 Schema：{"summary":"string","findings":["string"],'
        '"evidence":[{"fact":"string","source":"string","support":"string"}],'
        '"risks":["string"],"open_questions":["string"]}。findings 和 evidence 必须非空；risks 和 '
        "open_questions 没有内容时返回空数组。每项 evidence 必须说明事实、来源或工具以及它如何支持判断；"
        "禁止只汇报调用了多少工具。"
    )


def _repair_instruction(is_final: bool, validation_errors: list[str]) -> str:
    return (
        "上一条响应未通过结构化产物校验。只允许依据已经获得的内容修复 JSON 格式、字段类型和缺失字段；"
        "不得新增事实，不得调用工具，不得输出解释或代码围栏。"
        + _output_contract(is_final)
        + "校验错误："
        + "；".join(validation_errors)
    )


@dataclass(frozen=True)
class AgentExecutionConfig:
    key: str
    name: str
    role: str
    model: str
    temperature: float
    current_version: int
    system_prompt: str
    task_prompt: str
    tools_json: str
    skills: list[dict[str, str]]


def create_agent_run(
    db: Session,
    payload: AgentRunCreateRequest,
    agent_snapshots: list[dict[str, Any]] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> AgentRunRead:
    ensure_agent_run_schema(db)
    symbol = _normalize_symbol(payload.symbol)
    agents = _select_agents(db, payload.agent_keys, agent_snapshots)
    run_key = f"AR-{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    steps: list[AgentRunStep] = []
    agent_summaries: list[dict[str, Any]] = []
    variables = _build_variables(symbol, payload)

    for agent in agents:
        is_final = agent.key == FINAL_AGENT_KEY
        _emit_event(on_event, {"event_type": "agent_started", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "running", "payload": {"prompt_version": agent.current_version, "model": agent.model, "temperature": agent.temperature}})
        agent_steps, agent_response = _run_agent_tool_calls(
            db, agent, payload, variables, agent_summaries, run_key, on_event, is_final=is_final
        )
        steps.extend(agent_steps)
        artifact = _agent_summary(agent, agent_steps, agent_response, is_final=is_final)
        agent_summaries.append(artifact)
        _emit_event(on_event, {"event_type": "agent_completed", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": artifact["status"], "payload": {"step_count": len(agent_steps), "artifact": artifact}})

    result = _build_result(symbol, payload, agent_summaries, steps)
    failed_agents = [item for item in agent_summaries if item["status"] == "failed"]
    partial_agents = [item for item in agent_summaries if item["status"] == "partial"]
    status = "failed" if failed_agents else "partial" if partial_agents else "completed"
    if any(item["agent_key"] == FINAL_AGENT_KEY for item in agent_summaries) and not result["quality_gate"]["passed"]:
        status = "failed"
    result["snapshot_id"] = 0
    result["snapshot_summary"] = "任务未预取数据，所有数据均由智能体 tool_calls 获取。"
    run = AgentRun(
        run_key=run_key,
        symbol=symbol,
        query=payload.query,
        mode=payload.mode,
        status=status,
        snapshot_id=0,
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
        snapshot_id=run.snapshot_id,
        agent_keys=_json_list(run.agent_keys_json),
        steps=[AgentRunStep(**item) for item in _json_list_of_dict(run.steps_json)],
        result=_json_dict(run.result_json),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _select_agents(
    db: Session,
    agent_keys: list[str],
    agent_snapshots: list[dict[str, Any]] | None = None,
) -> list[AgentExecutionConfig]:
    if agent_snapshots:
        return [
            AgentExecutionConfig(
                key=str(item["key"]),
                name=str(item.get("name") or item["key"]),
                role=str(item.get("role") or ""),
                model=str(item.get("model") or ""),
                temperature=float(item.get("temperature") or 0.2),
                current_version=int(item.get("prompt_version") or 0),
                system_prompt=str(item.get("system_prompt") or ""),
                task_prompt=str(item.get("task_prompt") or ""),
                tools_json=json.dumps(item.get("tools") or [], ensure_ascii=False),
                skills=[item for item in item.get("skills") or [] if isinstance(item, dict)],
            )
            for item in agent_snapshots
            if isinstance(item, dict) and item.get("key")
        ]
    requested = agent_keys or DEFAULT_AGENT_PIPELINE
    rows = db.scalars(select(AgentConfig).where(AgentConfig.key.in_(requested))).all()
    by_key = {agent.key: agent for agent in rows if agent.enabled}
    return [
        AgentExecutionConfig(
            key=agent.key,
            name=agent.name,
            role=agent.role,
            model=agent.model,
            temperature=agent.temperature,
            current_version=agent.current_version,
            system_prompt=agent.system_prompt,
            task_prompt=agent.task_prompt,
            tools_json=agent.tools_json,
            skills=assigned_skill_catalog(db, agent.key),
        )
        for key in requested
        if (agent := by_key.get(key))
    ]


def ensure_agent_run_schema(db: Session) -> None:
    AgentRun.__table__.create(bind=db.get_bind(), checkfirst=True)
    existing = {row[1] for row in db.execute(text("PRAGMA table_info(agent_runs)")).all()}
    if "snapshot_id" not in existing:
        db.execute(text("ALTER TABLE agent_runs ADD COLUMN snapshot_id INTEGER DEFAULT 0"))
        db.commit()


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")


def _agent_tools(agent: AgentExecutionConfig) -> list[str]:
    return _json_list(agent.tools_json)


def _build_variables(symbol: str, payload: AgentRunCreateRequest) -> dict[str, str]:
    profile = get_stock_profile(symbol) if symbol else None
    values = {
        "stock_code": symbol,
        "stock_name": profile.name if profile else "",
        "analysis_subject": _task_subject(payload),
        "period": payload.period,
        "query": payload.query,
        "snapshot_summary": "任务未预取数据，按需调用工具获取证据。",
    }
    values.update(payload.variables)
    return values


def _run_agent_tool_calls(
    db: Session,
    agent: AgentExecutionConfig,
    payload: AgentRunCreateRequest,
    variables: dict[str, str],
    agent_summaries: list[dict[str, Any]],
    run_key: str,
    on_event: Callable[[dict[str, Any]], None] | None,
    *,
    is_final: bool,
) -> tuple[list[AgentRunStep], str]:
    runtime = get_model_runtime(db, "chat", agent.model)
    if not runtime.api_key:
        return [], ""

    allowed = _agent_tool_definitions(agent, payload.include_report)
    tool_by_function = {item["function"]["name"]: item["tool_key"] for item in allowed}
    messages, prompt_audit = _build_agent_messages(agent, payload, variables, agent_summaries, allowed, is_final=is_final)
    _emit_event(
        on_event,
        {
            "event_type": "agent_context",
            "run_key": run_key,
            "agent_key": agent.key,
            "agent_name": agent.name,
            "status": "ready",
            "payload": prompt_audit,
        },
    )
    steps: list[AgentRunStep] = []
    repair_attempts = 0
    tool_rounds = 0
    finalize_prompt_added = False
    last_response = ""
    for _ in range(8):
        force_json = repair_attempts > 0 or tool_rounds >= 5
        if force_json and not finalize_prompt_added:
            messages.append({"role": "user", "content": "工具调用阶段已经结束。现在必须直接返回最终结构化产物。" + _output_contract(is_final)})
            finalize_prompt_added = True
        turn_tools = [] if force_json else allowed
        message: dict[str, Any] | None = None
        for request_attempt in range(3):
            try:
                message = _request_agent_turn(db, agent.model, messages, turn_tools, agent.temperature)
                break
            except httpx.HTTPError as exc:
                retryable = _retryable_model_error(exc)
                will_retry = retryable and request_attempt < 2
                _emit_event(on_event, {"event_type": "model_response", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "retrying" if will_retry else "failed", "payload": {"error": str(exc), "retry": request_attempt + 1}})
                if not will_retry:
                    return steps, ""
            except (KeyError, ValueError) as exc:
                will_retry = request_attempt < 2
                _emit_event(on_event, {"event_type": "model_response", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "retrying" if will_retry else "failed", "payload": {"error": str(exc), "retry": request_attempt + 1}})
                if not will_retry:
                    return steps, ""
        if message is None:
            return steps, ""
        tool_calls = message.get("tool_calls") or []
        _emit_event(on_event, {"event_type": "model_response", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "completed", "payload": {"content": str(message.get("content") or ""), "tool_call_count": len(tool_calls) if isinstance(tool_calls, list) else 0}})
        if force_json and isinstance(tool_calls, list) and tool_calls:
            validation_errors = ["结构化输出阶段仍然请求了工具。"]
            if repair_attempts < 2:
                repair_attempts += 1
                messages.append({"role": "user", "content": _repair_instruction(is_final, validation_errors)})
                _emit_event(on_event, {"event_type": "artifact_repair", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "retrying", "payload": {"attempt": repair_attempts, "validation_errors": validation_errors}})
                continue
            return steps, last_response
        if not isinstance(tool_calls, list) or not tool_calls:
            last_response = str(message.get("content") or "")
            parsed = _parse_json_object(last_response)
            if is_final:
                parsed = _normalize_final_artifact(parsed)
            validation_errors = _validate_final_artifact(parsed) if is_final else _validate_stage_artifact(parsed)
            if validation_errors and repair_attempts < 2:
                if last_response:
                    messages.append({"role": "assistant", "content": last_response})
                repair_attempts += 1
                messages.append({"role": "user", "content": _repair_instruction(is_final, validation_errors)})
                _emit_event(on_event, {"event_type": "artifact_repair", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "status": "retrying", "payload": {"attempt": repair_attempts, "validation_errors": validation_errors}})
                continue
            return steps, last_response
        tool_rounds += 1
        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
        for tool_call in tool_calls[:8]:
            output: dict[str, Any] | None = None
            function = tool_call.get("function") if isinstance(tool_call, dict) else None
            function_name = function.get("name") if isinstance(function, dict) else ""
            tool_key = tool_by_function.get(str(function_name), str(function_name))
            params, parse_error = _tool_call_params(function)
            _emit_event(on_event, {"event_type": "tool_started", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "tool_key": tool_key, "status": "running", "payload": {"tool_call_id": str(tool_call.get("id") or ""), "params": params}})
            if function_name not in tool_by_function:
                step = AgentRunStep(
                    agent_key=agent.key,
                    agent_name=agent.name,
                    tool_key=tool_key,
                    status="failed",
                    error="模型请求了未授权工具。",
                )
            elif parse_error:
                step = AgentRunStep(
                    agent_key=agent.key,
                    agent_name=agent.name,
                    tool_key=tool_key,
                    status="failed",
                    error=parse_error,
                )
            else:
                try:
                    if tool_key == "skill.load":
                        output = load_assigned_skill(db, agent.key, str(params.get("skill_key") or ""), run_key)
                    else:
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
            steps.append(step)
            db.add(AgentToolCallAudit(agent_key=agent.key, tool_key=tool_key, status=step.status, error=step.error))
            db.commit()
            tool_message = {
                "tool_key": tool_key,
                "status": step.status,
                "output": output if step.status == "success" else None,
                "error": step.error,
            }
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call.get("id") or ""),
                    "content": json.dumps(tool_message, ensure_ascii=False, default=str),
                }
            )
            _emit_event(on_event, {"event_type": "tool_completed", "run_key": run_key, "agent_key": agent.key, "agent_name": agent.name, "tool_key": tool_key, "status": step.status, "payload": {"tool_call_id": str(tool_call.get("id") or ""), "params": params, "output": output if step.status == "success" else {}, "error": step.error}})
    return steps, last_response


def _build_agent_messages(
    agent: AgentExecutionConfig,
    payload: AgentRunCreateRequest,
    variables: dict[str, str],
    agent_summaries: list[dict[str, Any]],
    allowed_tools: list[dict[str, Any]],
    *,
    is_final: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workflow_instruction = str(payload.variables.get("workflow_instruction") or "").strip()
    render_variables = dict(variables)
    if not render_variables.get("stock_code"):
        render_variables["stock_code"] = render_variables.get("analysis_subject", "")
    if not render_variables.get("stock_name"):
        render_variables["stock_name"] = render_variables.get("analysis_subject", "")
    current_step_goal = _render(agent.task_prompt, render_variables).strip()
    output_contract = _output_contract(is_final)
    skill_catalog_instruction = (
        "可用 Skill 目录：" + json.dumps(agent.skills, ensure_ascii=False)
        + "。这里只提供名称和描述；确实需要某项方法时，调用 skill__load 获取完整 instruction，"
        "未加载的 Skill 不得假装已经遵循。"
        if agent.skills else ""
    )
    system_prompt = "\n\n".join(
        part
        for part in (
            _render(agent.system_prompt, variables).strip(),
            "多智能体执行契约：你只负责自己的专业职责，不替其他 Agent 代写结论；"
            "需要外部证据时必须使用已授权工具，不得猜测参数或虚构股票代码。",
            f"当前步骤目标：{current_step_goal}" if current_step_goal else "",
            f"任务工作流约束：{workflow_instruction}" if workflow_instruction else "",
            skill_catalog_instruction,
            output_contract,
        )
        if part
    )
    prior_artifacts = _prior_stage_context(agent_summaries, compact=True)
    user_context = {
        "user_requirement": payload.query,
        "current_agent": {"key": agent.key, "name": agent.name, "role": agent.role},
        "prior_stage_artifacts": prior_artifacts,
        "workflow_phase": "final_synthesis" if is_final else "specialist_analysis",
        "output_requirement": output_contract,
    }
    prompt_audit = {
        "user_requirement": payload.query,
        "agent_role": agent.role,
        "current_step_goal": current_step_goal,
        "system_prompt": system_prompt,
        "prior_stage_artifacts": prior_artifacts,
        "allowed_tools": [item["tool_key"] for item in allowed_tools],
        "available_skills": agent.skills,
        "prompt_version": agent.current_version,
        "workflow_phase": "final_synthesis" if is_final else "specialist_analysis",
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_context, ensure_ascii=False)},
    ], prompt_audit


def _prior_stage_context(agent_summaries: list[dict[str, Any]], *, compact: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "agent_key": item.get("agent_key", ""),
            "agent_name": item.get("agent_name", ""),
            "role": item.get("role", ""),
            "status": item.get("status", ""),
            "artifact": _compact_stage_artifact(item.get("artifact", {})) if compact else item.get("artifact", {}),
            "tool_evidence": item.get("bullets", [])[:6] if compact else item.get("bullets", []),
            "validation_errors": item.get("validation_errors", []),
        }
        for item in agent_summaries
    ]


def _compact_stage_artifact(artifact: Any) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        return {}
    limits = {"findings": 4, "evidence": 6, "risks": 4, "open_questions": 4}
    compact: dict[str, Any] = {}
    for key in ("summary", "findings", "evidence", "risks", "open_questions"):
        value = artifact.get(key)
        if isinstance(value, list):
            compact[key] = [_compact_context_value(item) for item in value[:limits.get(key, 4)]]
        elif isinstance(value, str):
            compact[key] = value[:800]
    return compact


def _compact_context_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return [_compact_context_value(item) for item in value[:5]]
    if isinstance(value, dict):
        return {str(key): _compact_context_value(item) for key, item in list(value.items())[:8]}
    return value


def _agent_tool_definitions(agent: AgentExecutionConfig, include_report: bool) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for tool_key in _agent_tools(agent):
        # Report persistence belongs to the workflow after the final artifact passes validation.
        if tool_key == "document.write":
            continue
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
                    "name": _tool_function_name(tool_key),
                    "description": spec.description,
                    "parameters": spec.input_schema or {"type": "object", "properties": {}},
                },
            }
        )
    if agent.skills:
        definitions.append(
            {
                "type": "function",
                "tool_key": "skill.load",
                "function": {
                    "name": "skill__load",
                    "description": "按需加载一个已授权 Skill 的完整 instruction。仅在当前任务确实需要该方法时调用。",
                    "parameters": {
                        "type": "object",
                        "required": ["skill_key"],
                        "properties": {
                            "skill_key": {
                                "type": "string",
                                "enum": [item["key"] for item in agent.skills],
                                "description": "要加载的已授权 Skill key",
                            }
                        },
                    },
                },
            }
        )
    return definitions


def _retryable_model_error(exc: httpx.HTTPError) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in {408, 409, 429} or status >= 500
    return isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.PoolTimeout,
        ),
    )


def _request_agent_turn(db: Session, preferred_model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]], temperature: float) -> dict[str, Any]:
    runtime = get_model_runtime(db, "chat", preferred_model)
    with httpx.Client(timeout=runtime.timeout_seconds) as client:
        request_body: dict[str, Any] = {
            "model": runtime.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            request_body["tools"] = [{"type": item["type"], "function": item["function"]} for item in tools]
            request_body["tool_choice"] = "auto"
        else:
            request_body["response_format"] = {"type": "json_object"}
        response = client.post(
            runtime.base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {runtime.api_key}", "Content-Type": "application/json"},
            json=request_body,
        )
        if not tools and response.status_code in {400, 422}:
            request_body.pop("response_format", None)
            response = client.post(
                runtime.base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {runtime.api_key}", "Content-Type": "application/json"},
                json=request_body,
            )
        response.raise_for_status()
    message = response.json()["choices"][0]["message"]
    if not isinstance(message, dict):
        raise ValueError("LLM tool-call response is not an object.")
    return message


def _tool_call_params(function: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(function, dict):
        return {}, "模型返回了无效的工具调用。"
    raw_arguments = str(function.get("arguments") or "{}").strip()
    if not raw_arguments.startswith("{"):
        return {}, "模型返回的工具参数不是 JSON 对象。"
    try:
        params = json.loads(raw_arguments)
    except json.JSONDecodeError:
        try:
            params = repair_json(raw_arguments, return_objects=True)
        except (ValueError, TypeError, OSError):
            return {}, "模型返回的工具参数不是有效 JSON。"
    return (params, "") if isinstance(params, dict) else ({}, "模型返回的工具参数必须是对象。")


def _tool_function_name(tool_key: str) -> str:
    return "tool__" + tool_key.replace(".", "_").replace("-", "_")


def _render(template: str, variables: dict[str, str]) -> str:
    result = template
    for key, value in variables.items():
        result = re.sub(r"{{\s*" + re.escape(key) + r"\s*}}", value, result)
    return result


def _emit_event(callback: Callable[[dict[str, Any]], None] | None, event: dict[str, Any]) -> None:
    if callback:
        callback(event)


def _agent_summary(
    agent: AgentExecutionConfig,
    steps: list[AgentRunStep],
    response: str,
    *,
    is_final: bool,
) -> dict[str, Any]:
    success = [step for step in steps if step.status == "success"]
    evidence_success = [step for step in success if step.tool_key != "skill.load"]
    failed = [step for step in steps if step.status != "success"]
    bullets = []
    for step in success:
        bullets.append(f"{step.tool_key}: {step.output_preview.get('summary', '已获取数据')}")
    for step in failed:
        bullets.append(f"{step.tool_key}: 失败，{step.error}")
    parsed = _parse_json_object(response)
    if is_final:
        parsed = _normalize_final_artifact(parsed)
    requires_tool_evidence = agent.key not in SYNTHESIS_AGENT_KEYS and bool(_agent_tools(agent))
    validation_errors = _validate_final_artifact(parsed) if is_final else _validate_stage_artifact(parsed)
    if not response.strip() or validation_errors or (requires_tool_evidence and not evidence_success):
        status = "failed"
    elif failed:
        status = "partial"
    else:
        status = "completed"
    return {
        "agent_key": agent.key,
        "agent_name": agent.name,
        "role": agent.role,
        "status": status,
        "phase": "final_synthesis" if is_final else "specialist_analysis",
        "tool_count": len(steps),
        "success_count": len(success),
        "bullets": bullets,
        "response": response,
        "artifact": parsed,
        "validation_errors": validation_errors,
    }


def _build_result(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
    steps: list[AgentRunStep],
) -> dict[str, Any]:
    final_stage = next((item for item in reversed(agent_summaries) if item["agent_key"] == FINAL_AGENT_KEY), None)
    artifact = final_stage.get("artifact", {}) if final_stage else {}
    quality_errors = _validate_final_artifact(artifact)
    result = {
        "symbol": symbol,
        "query": payload.query,
        "mode": payload.mode,
        "conclusion": str(artifact.get("conclusion") or ""),
        "horizon": str(artifact.get("horizon") or ""),
        "confidence": artifact.get("confidence", 0),
        "key_evidence": _string_items(artifact.get("key_evidence")),
        "risks": _string_items(artifact.get("risks")),
        "watch_items": _string_items(artifact.get("watch_items")),
        "summary": str(artifact.get("executive_summary") or ""),
        "title": str(artifact.get("title") or ""),
        "markdown_report": str(artifact.get("markdown_report") or ""),
        "agent_summaries": agent_summaries,
        "tool_success_count": sum(1 for step in steps if step.status == "success"),
        "tool_failed_count": sum(1 for step in steps if step.status != "success"),
        "quality_gate": {"passed": not quality_errors, "errors": quality_errors},
        "model_status": "agent_pipeline",
    }
    result["references"] = [
        {
            "agent_key": step.agent_key,
            "tool_key": step.tool_key,
            "status": step.status,
        }
        for step in steps
    ]
    return result


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        return {}

    candidates = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(text[first_brace:last_brace + 1])
    if text.startswith("{") and text.endswith("}"):
        candidates.append(text)

    if not candidates:
        return {}

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    for candidate in candidates:
        try:
            parsed = repair_json(candidate.strip(), return_objects=True)
        except (ValueError, TypeError, OSError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_final_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if not artifact:
        return artifact
    normalized = dict(artifact)

    confidence = _normalize_confidence(normalized.get("confidence"))
    if confidence is not None:
        normalized["confidence"] = confidence

    horizon = normalized.get("horizon")
    if isinstance(horizon, dict):
        labels = {
            "short_term": "短期",
            "medium_term": "中期",
            "long_term": "长期",
        }
        normalized["horizon"] = "；".join(
            f"{labels.get(str(key), str(key))}：{value}"
            for key, value in horizon.items()
            if str(value).strip()
        )
    elif isinstance(horizon, list):
        normalized["horizon"] = "；".join(str(item).strip() for item in horizon if str(item).strip())
    return normalized


def _normalize_confidence(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        confidence = round(float(value))
        return confidence if 0 <= confidence <= 100 else None
    text_value = str(value or "").strip()
    if not text_value:
        return None
    range_match = re.search(
        r"(100|\d{1,2})(?:\.\d+)?\s*[-~～—–至到]\s*(100|\d{1,2})(?:\.\d+)?\s*%?",
        text_value,
    )
    if range_match:
        low, high = (float(range_match.group(1)), float(range_match.group(2)))
        if 0 <= low <= 100 and 0 <= high <= 100:
            return round((low + high) / 2)
    percent_match = re.search(r"(100|\d{1,2})(?:\.\d+)?\s*%", text_value)
    if percent_match:
        return round(float(percent_match.group(1)))
    number_match = re.fullmatch(r"\s*(100|\d{1,2})(?:\.\d+)?\s*", text_value)
    return round(float(number_match.group(1))) if number_match else None


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        json.dumps(item, ensure_ascii=False, default=str) if isinstance(item, (dict, list)) else str(item).strip()
        for item in value
    ]


def _validate_final_artifact(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not artifact:
        return ["投研总监未返回结构化最终产物。"]
    for field, label in (("title", "标题"), ("conclusion", "结论"), ("executive_summary", "摘要"), ("horizon", "适用周期")):
        if not str(artifact.get(field) or "").strip():
            errors.append(f"最终产物缺少{label}。")
    for field, label in (("key_evidence", "关键证据"), ("risks", "主要风险"), ("watch_items", "观察项")):
        if not _string_items(artifact.get(field)):
            errors.append(f"最终产物缺少{label}。")
    markdown = str(artifact.get("markdown_report") or "").strip()
    if len(markdown) < 200 or "##" not in markdown:
        errors.append("最终 Markdown 报告内容不完整。")
    if any(marker in markdown for marker in ("工具编排完成", "本地规则摘要", "配置 LLM_API_KEY", "待补充")):
        errors.append("最终 Markdown 报告包含占位内容。")
    try:
        confidence = int(artifact.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1
    if confidence < 0 or confidence > 100:
        errors.append("最终产物置信度必须是 0 到 100 的整数。")
    return errors


def _validate_stage_artifact(artifact: dict[str, Any]) -> list[str]:
    if not artifact:
        return ["Agent 未返回结构化阶段产物。"]
    errors: list[str] = []
    if not str(artifact.get("summary") or "").strip():
        errors.append("阶段产物缺少摘要。")
    for field, label in (("findings", "分析发现"), ("evidence", "证据")):
        if not _string_items(artifact.get(field)):
            errors.append(f"阶段产物缺少{label}。")
    for field in ("risks", "open_questions"):
        if not isinstance(artifact.get(field), list):
            errors.append(f"阶段产物字段 {field} 必须是数组。")
    return errors


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


def _task_subject(payload: AgentRunCreateRequest) -> str:
    if payload.symbol.strip():
        return _normalize_symbol(payload.symbol)
    first_line = next((line.strip() for line in payload.query.splitlines() if line.strip()), "")
    return first_line[:60] or "综合市场分析"


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

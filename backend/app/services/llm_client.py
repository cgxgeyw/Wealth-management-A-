from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.agent_run import AgentRunCreateRequest, AgentRunStep
from app.services.analysis_task_templates import get_mode_protocol


def generate_run_conclusion(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
    steps: list[AgentRunStep],
) -> dict[str, Any]:
    success_count = sum(1 for step in steps if step.status == "success")
    failed_count = sum(1 for step in steps if step.status != "success")
    confidence = 0 if not steps else round((success_count / len(steps)) * 100)
    fallback = _fallback_conclusion(symbol, payload, agent_summaries, success_count, failed_count, confidence)
    if not settings.llm_api_key:
        return fallback | {"model_status": "fallback_no_api_key", "model": ""}

    try:
        result = _call_chat_completion(symbol, payload, agent_summaries, steps)
    except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return fallback | {
            "model_status": "fallback_llm_error",
            "model": settings.llm_model,
            "model_error": str(exc),
        }

    return fallback | result | {"model_status": "llm_completed", "model": settings.llm_model}


def _call_chat_completion(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
    steps: list[AgentRunStep],
) -> dict[str, Any]:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    messages = [
        {
            "role": "system",
            "content": (
                "你是谨慎的A股投研总监。只能基于给定工具结果总结，"
                "不要编造价格、新闻、财务数据。需要遵循当前任务模式的分析协议。输出严格JSON。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "symbol": symbol,
                    "query": payload.query,
                    "mode": payload.mode,
                    "mode_protocol": get_mode_protocol(payload.mode),
                    "agent_summaries": agent_summaries,
                    "tool_steps": [
                        {
                            "agent_key": step.agent_key,
                            "tool_key": step.tool_key,
                            "status": step.status,
                            "preview": step.output_preview,
                            "error": step.error,
                        }
                        for step in steps
                    ],
                    "required_json_schema": {
                        "conclusion": "一句话结论",
                        "horizon": "适用周期",
                        "confidence": "0-100整数",
                        "key_evidence": ["证据"],
                        "risks": ["风险"],
                        "watch_items": ["观察项"],
                        "summary": "简短说明",
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": messages,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    parsed = _parse_json_content(content)
    return {
        "conclusion": str(parsed.get("conclusion") or "模型已生成结论。"),
        "horizon": str(parsed.get("horizon") or ""),
        "confidence": _bounded_int(parsed.get("confidence"), 0, 100),
        "key_evidence": _string_list(parsed.get("key_evidence")),
        "risks": _string_list(parsed.get("risks")),
        "watch_items": _string_list(parsed.get("watch_items")),
        "summary": str(parsed.get("summary") or ""),
    }


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object.")
    return parsed


def _fallback_conclusion(
    symbol: str,
    payload: AgentRunCreateRequest,
    agent_summaries: list[dict[str, Any]],
    success_count: int,
    failed_count: int,
    confidence: int,
) -> dict[str, Any]:
    evidence = [
        f"{item['agent_name']} 成功执行 {item['success_count']}/{item['tool_count']} 个工具"
        for item in agent_summaries
    ]
    risks = []
    if failed_count:
        risks.append(f"{failed_count} 个工具执行失败，结论完整性受限")
    if not evidence:
        risks.append("没有可用工具结果")
    return {
        "symbol": symbol,
        "query": payload.query,
        "mode": payload.mode,
        "conclusion": "工具编排完成，模型未配置，当前为本地规则摘要。",
        "horizon": payload.period,
        "confidence": confidence,
        "key_evidence": evidence[:8],
        "risks": risks,
        "watch_items": ["配置 LLM_API_KEY 后可生成模型投研结论"],
        "summary": "系统已完成真实工具调用和上下文汇总。",
        "tool_success_count": success_count,
        "tool_failed_count": failed_count,
        "agent_summaries": agent_summaries,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return minimum
    return min(max(parsed, minimum), maximum)

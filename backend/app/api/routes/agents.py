import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentConfig, AgentPromptVersion
from app.schemas.agent import (
    AgentListResponse,
    AgentPromptVersionListResponse,
    AgentPromptVersionRead,
    AgentRead,
    AgentRenderRequest,
    AgentRenderResponse,
    AgentRollbackRequest,
    AgentTestRunRequest,
    AgentTestRunResponse,
    AgentUpdateRequest,
)

router = APIRouter()


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _variable_name(value: str) -> str:
    return value.strip().removeprefix("{{").removesuffix("}}").strip()


def _agent_read(agent: AgentConfig) -> AgentRead:
    return AgentRead(
        id=agent.id,
        key=agent.key,
        name=agent.name,
        role=agent.role,
        description=agent.description,
        model=agent.model,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        enabled=agent.enabled,
        system_prompt=agent.system_prompt,
        task_prompt=agent.task_prompt,
        output_schema=agent.output_schema,
        variables=_json_list(agent.variables_json),
        tools=_json_list(agent.tools_json),
        current_version=agent.current_version,
        updated_at=agent.updated_at,
    )


def _version_read(version: AgentPromptVersion) -> AgentPromptVersionRead:
    return AgentPromptVersionRead(
        id=version.id,
        agent_key=version.agent_key,
        version=version.version,
        system_prompt=version.system_prompt,
        task_prompt=version.task_prompt,
        output_schema=version.output_schema,
        variables=_json_list(version.variables_json),
        tools=_json_list(version.tools_json),
        change_note=version.change_note,
        created_at=version.created_at,
    )


def _get_agent(db: Session, agent_key: str) -> AgentConfig:
    agent = db.scalar(select(AgentConfig).where(AgentConfig.key == agent_key))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


@router.get("", response_model=AgentListResponse)
def list_agents(db: Session = Depends(get_db)) -> AgentListResponse:
    agents = db.scalars(select(AgentConfig).order_by(AgentConfig.id)).all()
    return AgentListResponse(items=[_agent_read(agent) for agent in agents])


@router.get("/{agent_key}", response_model=AgentRead)
def get_agent(agent_key: str, db: Session = Depends(get_db)) -> AgentRead:
    return _agent_read(_get_agent(db, agent_key))


@router.patch("/{agent_key}", response_model=AgentRead)
def update_agent(
    agent_key: str,
    payload: AgentUpdateRequest,
    db: Session = Depends(get_db),
) -> AgentRead:
    agent = _get_agent(db, agent_key)
    for field in ("name", "role", "description", "model", "system_prompt", "task_prompt", "output_schema"):
        value = getattr(payload, field)
        if value is not None:
            setattr(agent, field, value)
    if payload.temperature is not None:
        agent.temperature = payload.temperature
    if payload.max_tokens is not None:
        agent.max_tokens = payload.max_tokens
    if payload.enabled is not None:
        agent.enabled = payload.enabled
    if payload.variables is not None:
        agent.variables_json = json.dumps(payload.variables, ensure_ascii=False)
    if payload.tools is not None:
        agent.tools_json = json.dumps(payload.tools, ensure_ascii=False)

    next_version = agent.current_version + 1
    agent.current_version = next_version
    db.add(agent)
    db.add(
        AgentPromptVersion(
            agent_key=agent.key,
            version=next_version,
            system_prompt=agent.system_prompt,
            task_prompt=agent.task_prompt,
            output_schema=agent.output_schema,
            variables_json=agent.variables_json,
            tools_json=agent.tools_json,
            change_note=payload.change_note or "更新提示词配置",
        )
    )
    db.commit()
    db.refresh(agent)
    return _agent_read(agent)


@router.get("/{agent_key}/versions", response_model=AgentPromptVersionListResponse)
def list_versions(agent_key: str, db: Session = Depends(get_db)) -> AgentPromptVersionListResponse:
    _get_agent(db, agent_key)
    versions = db.scalars(
        select(AgentPromptVersion)
        .where(AgentPromptVersion.agent_key == agent_key)
        .order_by(desc(AgentPromptVersion.version))
    ).all()
    return AgentPromptVersionListResponse(items=[_version_read(version) for version in versions])


@router.post("/{agent_key}/rollback", response_model=AgentRead)
def rollback_agent(
    agent_key: str,
    payload: AgentRollbackRequest,
    db: Session = Depends(get_db),
) -> AgentRead:
    agent = _get_agent(db, agent_key)
    version = db.scalar(
        select(AgentPromptVersion).where(
            AgentPromptVersion.agent_key == agent_key,
            AgentPromptVersion.version == payload.version,
        )
    )
    if not version:
        raise HTTPException(status_code=404, detail="Prompt version not found.")
    agent.system_prompt = version.system_prompt
    agent.task_prompt = version.task_prompt
    agent.output_schema = version.output_schema
    agent.variables_json = version.variables_json
    agent.tools_json = version.tools_json
    agent.current_version += 1
    db.add(agent)
    db.add(
        AgentPromptVersion(
            agent_key=agent.key,
            version=agent.current_version,
            system_prompt=agent.system_prompt,
            task_prompt=agent.task_prompt,
            output_schema=agent.output_schema,
            variables_json=agent.variables_json,
            tools_json=agent.tools_json,
            change_note=payload.change_note,
        )
    )
    db.commit()
    db.refresh(agent)
    return _agent_read(agent)


@router.post("/{agent_key}/render", response_model=AgentRenderResponse)
def render_agent_prompt(
    agent_key: str,
    payload: AgentRenderRequest,
    db: Session = Depends(get_db),
) -> AgentRenderResponse:
    agent = _get_agent(db, agent_key)
    return _render_agent(agent, payload.variables)


@router.post("/{agent_key}/test-run", response_model=AgentTestRunResponse)
def test_run_agent(
    agent_key: str,
    payload: AgentTestRunRequest,
    db: Session = Depends(get_db),
) -> AgentTestRunResponse:
    agent = _get_agent(db, agent_key)
    rendered = _render_agent(agent, payload.variables)
    combined = f"{rendered.rendered_system_prompt}\n{rendered.rendered_task_prompt}\n{payload.input_text}"
    return AgentTestRunResponse(
        agent_key=agent.key,
        status="preview_only",
        rendered_prompt=rendered,
        model=agent.model,
        estimated_tokens=max(len(combined) // 2, 1),
        output="测试运行当前为提示词渲染预览，尚未接入真实模型调用。",
    )


def _render_agent(agent: AgentConfig, variables: dict[str, str]) -> AgentRenderResponse:
    declared_variables = [_variable_name(item) for item in _json_list(agent.variables_json)]
    all_names = set(declared_variables)
    all_names.update(re.findall(r"{{\s*([a-zA-Z0-9_]+)\s*}}", agent.system_prompt + agent.task_prompt))
    missing: list[str] = []

    def replace(text: str) -> str:
        result = text
        for name in sorted(all_names):
            token = "{{" + name + "}}"
            value = variables.get(name)
            if value is None:
                missing.append(name)
                continue
            result = re.sub(r"{{\s*" + re.escape(name) + r"\s*}}", value, result)
        return result

    return AgentRenderResponse(
        agent_key=agent.key,
        rendered_system_prompt=replace(agent.system_prompt),
        rendered_task_prompt=replace(agent.task_prompt),
        output_schema=agent.output_schema,
        missing_variables=sorted(set(missing)),
        tools=_json_list(agent.tools_json),
    )

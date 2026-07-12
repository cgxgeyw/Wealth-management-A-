from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentConfig
from app.models.agent_skill import AgentSkill, AgentSkillAssignment
from app.models.agent_audit import AgentSkillUsageAudit
from app.schemas.agent_skill import (
    AgentSkillCreateRequest,
    AgentSkillListResponse,
    AgentSkillRead,
    AgentSkillUpdateRequest,
)

router = APIRouter()


def _read_skill(db: Session, skill: AgentSkill) -> AgentSkillRead:
    agent_keys = db.scalars(
        select(AgentSkillAssignment.agent_key)
        .where(AgentSkillAssignment.skill_key == skill.key)
        .order_by(AgentSkillAssignment.agent_key)
    ).all()
    usage_count, last_used_at = db.execute(select(func.count(AgentSkillUsageAudit.id), func.max(AgentSkillUsageAudit.created_at)).where(AgentSkillUsageAudit.skill_key == skill.key)).one()
    return AgentSkillRead(
        id=skill.id,
        key=skill.key,
        name=skill.name,
        description=skill.description,
        instruction=skill.instruction,
        enabled=skill.enabled,
        agent_keys=agent_keys,
        usage_count=int(usage_count or 0),
        last_used_at=last_used_at,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _replace_assignments(db: Session, skill_key: str, agent_keys: list[str]) -> None:
    valid_keys = set(db.scalars(select(AgentConfig.key).where(AgentConfig.key.in_(agent_keys))).all())
    if len(valid_keys) != len(set(agent_keys)):
        raise HTTPException(status_code=400, detail="One or more assigned agents do not exist.")
    existing = db.scalars(select(AgentSkillAssignment).where(AgentSkillAssignment.skill_key == skill_key)).all()
    for assignment in existing:
        db.delete(assignment)
    for agent_key in sorted(valid_keys):
        db.add(AgentSkillAssignment(agent_key=agent_key, skill_key=skill_key))


@router.get("", response_model=AgentSkillListResponse)
def list_agent_skills(db: Session = Depends(get_db)) -> AgentSkillListResponse:
    skills = db.scalars(select(AgentSkill).order_by(AgentSkill.key)).all()
    return AgentSkillListResponse(items=[_read_skill(db, skill) for skill in skills])


@router.post("", response_model=AgentSkillRead)
def create_agent_skill(payload: AgentSkillCreateRequest, db: Session = Depends(get_db)) -> AgentSkillRead:
    if db.scalar(select(AgentSkill).where(AgentSkill.key == payload.key)):
        raise HTTPException(status_code=409, detail="Skill key already exists.")
    skill = AgentSkill(
        key=payload.key,
        name=payload.name,
        description=payload.description,
        instruction=payload.instruction,
        enabled=payload.enabled,
    )
    db.add(skill)
    db.flush()
    _replace_assignments(db, skill.key, payload.agent_keys)
    db.commit()
    db.refresh(skill)
    return _read_skill(db, skill)


@router.patch("/{skill_key}", response_model=AgentSkillRead)
def update_agent_skill(
    skill_key: str,
    payload: AgentSkillUpdateRequest,
    db: Session = Depends(get_db),
) -> AgentSkillRead:
    skill = db.scalar(select(AgentSkill).where(AgentSkill.key == skill_key))
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found.")
    for field in ("name", "description", "instruction", "enabled"):
        value = getattr(payload, field)
        if value is not None:
            setattr(skill, field, value)
    if payload.agent_keys is not None:
        _replace_assignments(db, skill.key, payload.agent_keys)
    db.commit()
    db.refresh(skill)
    return _read_skill(db, skill)


@router.delete("/{skill_key}", status_code=204)
def delete_agent_skill(skill_key: str, db: Session = Depends(get_db)) -> None:
    skill = db.scalar(select(AgentSkill).where(AgentSkill.key == skill_key))
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found.")
    for assignment in db.scalars(select(AgentSkillAssignment).where(AgentSkillAssignment.skill_key == skill_key)).all():
        db.delete(assignment)
    db.delete(skill)
    db.commit()

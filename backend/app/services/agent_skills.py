from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_skill import AgentSkill, AgentSkillAssignment
from app.models.agent_audit import AgentSkillUsageAudit


def assigned_skills(db: Session, agent_key: str) -> list[AgentSkill]:
    return db.scalars(
        select(AgentSkill)
        .join(AgentSkillAssignment, AgentSkillAssignment.skill_key == AgentSkill.key)
        .where(AgentSkillAssignment.agent_key == agent_key, AgentSkill.enabled.is_(True))
        .order_by(AgentSkill.key)
    ).all()


def assigned_skill_instructions(db: Session, agent_key: str) -> str:
    skills = assigned_skills(db, agent_key)
    if not skills:
        return ""
    sections = [f"[{skill.name}]\n{skill.instruction.strip()}" for skill in skills if skill.instruction.strip()]
    return "\n\n".join(sections)


def assigned_skill_catalog(db: Session, agent_key: str) -> list[dict[str, str]]:
    return [
        {"key": skill.key, "name": skill.name, "description": skill.description}
        for skill in assigned_skills(db, agent_key)
    ]


def load_assigned_skill(db: Session, agent_key: str, skill_key: str, run_key: str = "") -> dict[str, str]:
    skill = next((item for item in assigned_skills(db, agent_key) if item.key == skill_key), None)
    if not skill:
        raise ValueError("Skill 未启用或未授权给当前 Agent。")
    db.add(AgentSkillUsageAudit(agent_key=agent_key, skill_key=skill.key, run_key=run_key))
    return {
        "skill_key": skill.key,
        "name": skill.name,
        "description": skill.description,
        "instruction": skill.instruction,
    }


def record_skill_usage(db: Session, agent_key: str, run_key: str = "") -> None:
    for skill in assigned_skills(db, agent_key):
        db.add(AgentSkillUsageAudit(agent_key=agent_key, skill_key=skill.key, run_key=run_key))

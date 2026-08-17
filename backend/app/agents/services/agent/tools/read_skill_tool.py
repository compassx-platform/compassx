"""read_skill tool — reads the full content of an attached skill by name."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session, selectinload

from app.models.agents import Agent, AgentSkillAttachment
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class ReadSkillTool(BaseTool):
    key = "read_skill"
    name = "Read Skill"
    description = (
        "Retrieve the full markdown instructions (body) of a specific attached skill by its exact name. "
        "Use this tool to read step-by-step procedural guidelines before executing a task."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "The exact name of the skill to read",
            }
        },
        "required": ["skill_name"],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        skill_name = args.get("skill_name", "").strip()
        if not skill_name:
            return ToolResult(ok=False, error="skill_name argument is required")

        # Load skills attached to this agent
        attachments = (
            db.query(AgentSkillAttachment)
            .options(selectinload(AgentSkillAttachment.skill))
            .filter(AgentSkillAttachment.agent_id == agent.id)
            .all()
        )

        target_attachment = None
        for att in attachments:
            if att.skill and att.skill.is_active and att.skill.name.lower() == skill_name.lower():
                target_attachment = att
                break

        if not target_attachment:
            return ToolResult(
                ok=False,
                error=f"Skill '{skill_name}' is not attached to this agent or is not found.",
            )

        skill = target_attachment.skill
        return ToolResult(
            ok=True,
            result={
                "name": skill.name,
                "description": skill.description,
                "body": skill.body,
                "version": skill.version,
                "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
            },
        )

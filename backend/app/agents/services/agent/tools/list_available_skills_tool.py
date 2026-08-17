"""list_available_skills tool — lists skills attached to the current agent."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session, selectinload

from app.models.agents import Agent, AgentSkillAttachment
from app.agents.services.agent.tools.base_tool import BaseTool, ToolResult


class ListAvailableSkillsTool(BaseTool):
    key = "list_available_skills"
    name = "List Available Skills"
    description = (
        "Discover the procedural instructions and skills attached to this agent. "
        "Returns a list of skills containing their name, description, trigger hints, and version. "
        "Use this tool to see what specialized procedures are available before executing one."
    )
    is_async = False
    input_schema = {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional search term to filter available skills by name or description",
            }
        },
        "required": [],
    }

    def execute(self, args: dict[str, Any], agent: Agent, db: Session) -> ToolResult:
        # Load skills attached to this agent
        attachments = (
            db.query(AgentSkillAttachment)
            .options(selectinload(AgentSkillAttachment.skill))
            .filter(AgentSkillAttachment.agent_id == agent.id)
            .order_by(AgentSkillAttachment.position)
            .all()
        )

        search = args.get("search")
        results = []
        for att in attachments:
            skill = att.skill
            if not skill or not skill.is_active:
                continue
            
            # Apply search filter if provided
            if search:
                search_lower = search.lower()
                if search_lower not in skill.name.lower() and search_lower not in skill.description.lower():
                    continue

            results.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "trigger_hints": skill.trigger_hints,
                "version": skill.version,
            })

        return ToolResult(ok=True, result={"skills": results})

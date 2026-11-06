"""FastAPI routes for the Agent Runtime Module."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.agent_runtime.models import (
    AgentChatMessage,
    AgentRuntimeSession,
    CreateAgentSessionRequest,
    SendMessageRequest,
)

from app.agent_runtime.service import agent_runtime_service

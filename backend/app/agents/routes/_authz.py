"""Authorisation helpers shared by the agent routes.

Every route in this package resolves one of two securables:

  * the **agent** — for its definition, its sessions, and anything produced
    inside a session (messages, plans, documents, artifacts, changes);
  * a **connection** — for database, LLM, git, and external connections, which
    are what an agent reaches data and models through.

Both are workspace-scoped: they carry no catalog path, so a lookup must be
filtered by workspace *before* the grant check. Otherwise a grant held in
workspace A would be evaluated against an object in workspace B, and an id
from another workspace would resolve.

Privilege choices
-----------------
``BROWSE`` reads a definition, ``EDIT`` changes it, ``MANAGE`` deletes it or
changes who may use it, and ``EXECUTE`` runs it. For an agent, EXECUTE is the
consequential one: a chat turn runs tools under the agent's service identity,
so it is a delegation of that identity's data access rather than permission to
type in a box.

Sessions belong to their agent
------------------------------
A session, its messages, its uploaded documents, and the changes an agent
proposes are all governed by the agent that owns them; they have no grants of
their own. Resolving the agent first is also what scopes the lookup — session
and document ids are globally unique, so an unscoped query happily returns
another workspace's rows.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.governance.dependencies import Guard
from app.governance.privileges import Privilege
from app.governance.securable import Securable


def workspace_id_of(request: Request) -> str:
    """The workspace a request is addressed to.

    Read from the resolved context, never from a body or query parameter — a
    caller must not get to name the workspace in which they happen to hold a
    grant.
    """
    ctx = getattr(request.state, "workspace", None)
    if ctx is None:
        raise HTTPException(
            status_code=400,
            detail="No workspace context. Address this endpoint under /w/<workspace>.",
        )
    return str(ctx.workspace_id)


# ── agents ────────────────────────────────────────────────────────────────────


def authorized_agent(db, guard: Guard, agent_id: int | str, privilege: Privilege):
    """Load an agent the caller holds ``privilege`` on, or raise 404/403."""
    from app.models.agents import Agent

    agent = (
        db.query(Agent)
        .filter(
            Agent.id == agent_id,
            Agent.workspace_id == guard.workspace_id,
        )
        .first()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    guard.require(privilege, Securable.agent(str(agent.id)))
    return agent


def visible_agents(guard: Guard, agents, privilege: Privilege = Privilege.BROWSE):
    """Narrow a list of agents to those the caller may see.

    List endpoints filter; they never refuse.
    """
    return guard.filter(privilege, agents, lambda a: Securable.agent(str(a.id)))


def authorized_session(db, guard: Guard, agent_id: int | str, session_id, privilege: Privilege):
    """Load a chat session in an agent the caller holds ``privilege`` on.

    The agent is resolved first, which both authorises the read and scopes it:
    session ids are globally unique, so filtering by id alone would return
    sessions belonging to agents in other workspaces.
    """
    from app.models.agents import ChatSession

    agent = authorized_agent(db, guard, agent_id, privilege)
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.agent_id == agent.id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── connections ───────────────────────────────────────────────────────────────


def authorized_connection(db, guard: Guard, model, connection_id, privilege: Privilege):
    """Load a connection the caller holds ``privilege`` on, or raise.

    ``model`` is the connection table in question (database, LLM, git,
    external). They are governed uniformly: all four are credentials pointing
    at a system outside the platform, and reaching any of them is reaching
    whatever that system holds.

    ``USE_COMPUTE`` is the "may run through this" privilege for connections —
    the same one compute uses — so a member who may see that a connection
    exists is not thereby entitled to query through it.
    """
    row = (
        db.query(model)
        .filter(
            model.id == connection_id,
            model.workspace_id == guard.workspace_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    guard.require(privilege, Securable.connection(str(row.id)))
    return row


def visible_connections(guard: Guard, rows, privilege: Privilege = Privilege.BROWSE):
    """Narrow a list of connections to those the caller may see."""
    return guard.filter(privilege, rows, lambda c: Securable.connection(str(c.id)))

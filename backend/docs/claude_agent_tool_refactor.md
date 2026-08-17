# Claude Agent Tool — Refactoring Plan

## Context

This document captures the design and implementation plan for refactoring
`claude_agent_tool.py` and `git_workspace_tool.py` to follow SOLID principles
and make the codebase easier to extend in the future.

---

## Problems with the Current Code

### 1. Naming collision: `workspace`
The term **workspace** is used in two different, overlapping senses:
- **Agent workspace** — the agent's execution environment / session context.
- **Git workspace** — the cloned repo + worktree directory set up by `GitWorkspaceTool`.

In `claude_agent_tool.py`, variables like `workspace_info`, `worktree_path`, and the
`workspace_preamble` block all refer to the *git* workspace, but the naming
makes it easy to confuse the two concepts.

**Resolution:** rename all git-workspace-related identifiers in `ClaudeAgentTool`
to use the prefix `git_workspace_` or call the setup result `git_workspace_info`.
The `GitWorkspaceTool.execute()` return key `worktree_path` becomes `git_worktree_path`
in the consuming code's local variables.

---

### 2. Single Responsibility Principle (SRP) violations

`claude_agent_tool.py` currently owns:
- PAT resolution (`_get_pat`) — duplicated from `git_workspace_tool.py`
- GitHub API operations (PR, comment, work item) — 5 functions
- Azure DevOps API operations (PR, comment, work item) — 5 functions
- Diff fetching (GitHub + ADO) — 2 functions
- MCP server construction (`_build_mcp_server`)
- Agentic LLM loop with inline tool dispatch (`_invoke_via_llm_connection`)
- Claude CLI subprocess wrapper (`_invoke_claude_cli`)
- Claude SDK wrapper (`_invoke_claude_sdk`)
- Orchestrating code-review pipeline (`_run_code_review`)
- Orchestrating code-generation pipeline (`_run_generate_code`)

Each of these is a separate responsibility and should live in its own module.

---

### 3. Open/Closed Principle (OCP) violations

Adding a new provider (e.g. GitLab) today requires editing `claude_agent_tool.py`
in multiple `if provider == "azure_devops"` branches. The code is not closed for
modification — a new provider forces changes in every dispatch point.

---

### 4. Dependency Inversion Principle (DIP) violations

`ClaudeAgentTool._run_generate_code` directly instantiates `GitWorkspaceTool`
and calls `.execute()` on it. High-level orchestration code depends on a
concrete low-level class, not an abstraction.

---

### 5. Duplicated `_get_pat`

`_get_pat` is copy-pasted in both `claude_agent_tool.py` and
`git_workspace_tool.py`. Any change must be applied in two places.

---

## Proposed File Structure

```
backend/app/services/agent/tools/
├── base_tool.py                  (unchanged)
├── git_workspace_tool.py         (keep, minor rename fixes)
│
├── providers/
│   ├── __init__.py
│   ├── base_provider.py          # Abstract provider interface (OCP)
│   ├── github_provider.py        # GitHub implementations
│   └── ado_provider.py           # Azure DevOps implementations
│
├── auth/
│   ├── __init__.py
│   └── pat_resolver.py           # Single _get_pat() source of truth (DRY)
│
├── claude_agent/
│   ├── __init__.py
│   ├── claude_agent_tool.py      # Thin orchestrator (SRP, DIP)
│   ├── code_review_pipeline.py   # _run_code_review logic (SRP)
│   ├── code_generate_pipeline.py # _run_generate_code logic (SRP)
│   ├── llm_invoker.py            # _ask_claude_text / _invoke_via_llm_connection (SRP)
│   └── sub_tool_dispatcher.py    # Tool dispatch map (OCP — add new tools here)
```

> **Note:** The existing `claude_agent_tool.py` import path must remain importable
> as `app.services.agent.tools.claude_agent_tool` to avoid breaking the tool registry.
> The new `claude_agent/` package can export the class from its `__init__.py`.

---

## Workspace Naming Convention (Key Change)

| Old name (ambiguous) | New name (unambiguous) |
|---|---|
| `workspace_info` | `git_workspace_info` |
| `worktree_path` (local var in ClaudeAgentTool) | `git_worktree_path` |
| `workspace_preamble` | `git_workspace_preamble` |
| `GitWorkspaceTool` result key `"message"` text | unchanged (returned to LLM) |
| `AGENT_WORKSPACE_ROOT` env var | unchanged (controls where git clones live) |

The `worktree_path` key in the **input schema** of `ClaudeAgentTool` stays
`worktree_path` (breaking change to callers if renamed). But internally the
variable holding the resolved path is renamed `git_worktree_path`.

---

## SOLID Refactoring Details

### S — Single Responsibility

**`pat_resolver.py`**
```python
def get_pat(agent: Agent | None, provider: str) -> str: ...
```
Single file owns PAT lookup. Both `git_workspace_tool.py` and
`claude_agent_tool.py` import from here.

**`providers/base_provider.py`**
```python
from abc import ABC, abstractmethod

class GitProvider(ABC):
    @abstractmethod
    def create_pr(self, args: dict, token: str) -> dict: ...
    @abstractmethod
    def post_pr_comment(self, args: dict, token: str) -> dict: ...
    @abstractmethod
    def post_workitem_comment(self, args: dict, token: str) -> dict: ...
    @abstractmethod
    def set_pr_ready(self, args: dict, token: str) -> dict: ...
    @abstractmethod
    def update_workitem_status(self, args: dict, token: str) -> dict: ...
    @abstractmethod
    def fetch_pr_diff(self, args: dict, token: str) -> dict: ...
```

**`providers/github_provider.py`** — all `_*_github` functions become methods.

**`providers/ado_provider.py`** — all `_*_ado` functions become methods.

### O — Open/Closed

A provider registry replaces all `if provider == "azure_devops"` branches:

```python
# sub_tool_dispatcher.py
_PROVIDERS: dict[str, GitProvider] = {
    "github": GitHubProvider(),
    "azure_devops": AzureDevOpsProvider(),
}

def get_provider(name: str) -> GitProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"Unsupported provider: {name}")
    return _PROVIDERS[name]
```

Adding GitLab later = add `_PROVIDERS["gitlab"] = GitLabProvider()`. No existing
code needs to change.

### L — Liskov Substitution

All providers satisfy the `GitProvider` interface. The orchestrator only
calls methods defined on `GitProvider`, so any concrete provider is substitutable.

### I — Interface Segregation

The `GitProvider` interface is split into composable mixins if needed:
- `PRProvider` — create_pr, post_pr_comment, set_pr_ready
- `WorkItemProvider` — post_workitem_comment, update_workitem_status
- `DiffProvider` — fetch_pr_diff

A provider only implements the interfaces it supports.

### D — Dependency Inversion

`ClaudeAgentTool` depends on the `GitProvider` abstraction, not concrete classes.
`_run_generate_code` receives a `WorkspaceSetup` protocol instead of directly
instantiating `GitWorkspaceTool`:

```python
class WorkspaceSetup(Protocol):
    def setup(self, args: dict, agent: Agent) -> ToolResult: ...

class GitWorkspaceSetup:
    def setup(self, args: dict, agent: Agent) -> ToolResult:
        return GitWorkspaceTool().execute(args, agent, db=None)
```

---

## Key Invariants (Must Not Break)

1. `ClaudeAgentTool.execute()` signature: `(args, agent, db) -> ToolResult`
2. Input schema keys: `action`, `prompt`, `repo`, `pr_number`, `provider`,
   `organization`, `project`, `worktree_path`, `session_id`, `workitem_id`
3. `GitWorkspaceTool.execute()` return keys: `worktree_path`, `clone_path`,
   `branch`, `base_branch`, `head_commit`, `repo_url`, `message`
4. The tool registry key `claude_agent` must remain unchanged.
5. `AGENT_WORKSPACE_ROOT` env var must keep controlling the git workspace root.
6. PAT injection logic and provider fallback env vars (`ADO_PAT`, `GITHUB_TOKEN`)
   must behave identically after refactor.

---

## Implementation Order

1. **Create `auth/pat_resolver.py`** — extract `_get_pat`, update both tool files to import it.
2. **Create `providers/base_provider.py`** — define `GitProvider` ABC.
3. **Create `providers/github_provider.py`** — migrate all `_*_github` functions.
4. **Create `providers/ado_provider.py`** — migrate all `_*_ado` functions.
5. **Create `providers/__init__.py`** with `get_provider()` registry.
6. **Create `claude_agent/llm_invoker.py`** — extract `_ask_claude_text`, `_invoke_via_llm_connection`, `_invoke_claude_cli`, `_invoke_claude_sdk`.
7. **Create `claude_agent/sub_tool_dispatcher.py`** — extract `_dispatch` logic, use provider registry.
8. **Create `claude_agent/code_review_pipeline.py`** — extract `_run_code_review`.
9. **Create `claude_agent/code_generate_pipeline.py`** — extract `_run_generate_code`, rename `workspace_info` → `git_workspace_info`.
10. **Slim down `claude_agent_tool.py`** — thin `ClaudeAgentTool` class that delegates to the above.
11. **Update `git_workspace_tool.py`** — import `get_pat` from `auth/pat_resolver.py`, remove local copy.
12. **Verify** all existing tests pass; run integration smoke test for code_review and generate_code actions.

---

## Notes for Future Extension

- To add a **new action** (e.g. `run_tests`): add a new pipeline module and a
  new `elif` in `ClaudeAgentTool.execute()`. All other modules are untouched.
- To add a **new provider** (e.g. GitLab): implement `GitProvider`, register in
  `providers/__init__.py`. Zero changes to pipeline or dispatcher code.
- To swap the **LLM backend**: only `llm_invoker.py` needs to change.

  Agent → Claude Code SDK: Full Process                                   
  
  1. User Sends a Message                                                 
                                                            
  The frontend sends a chat message to POST /api/chat/{agent_id}/message.
  The agent has:                                            
  - An LLM connection (LiteLLM proxy pointing to Azure OpenAI or
  Anthropic)
  - A Git connection (ADO PAT encrypted in DB)
  - A system prompt describing its capabilities

  ---
  2. Orchestrator Receives the Task

  AgentOrchestrator.run() picks up the message and calls the outer LLM
  (via chat_stream) to decide which tool to invoke. The outer LLM reads
  the agent's system prompt and tool definitions and emits a tool-call
  like:

  {
    "tool": "claude_agent",
    "action": "generate_code",
    "repo_url":
  "https://dev.azure.com/IpPlatform/IDCC/_git/asset_maintenance_backend",
    "branch_name": "feature/update-readme",
    "provider": "azure_devops",
    "prompt": "Refine the README and create a PR"
  }

  ---
  3. ClaudeAgentTool.execute() is Called

  claude_agent_tool.py dispatches to _run_generate_code(args, agent) based
   on action == "generate_code".

  ---
  4. Phase 0 — Git Workspace Setup

  _run_generate_code
    └── validate worktree_path (Path.is_dir())
         └── if missing/invalid → GitWorkspaceTool.execute()

  GitWorkspaceTool does:
  1. Resolves PAT — calls _get_pat(agent, "azure_devops") which decrypts
  gc.pat_enc from the agent's git_connections relationship
  2. Injects PAT into URL — https://:{pat}@dev.azure.com/IpPlatform/IDCC/_
  git/asset_maintenance_backend
  3. Clones into
  AGENT_WORKSPACE_ROOT/IpPlatform_IDCC__git_asset_maintenance_backend/
  with --no-single-branch --depth 1
  4. Auto-detects default branch — tries development → develop → master →
  main → git symbolic-ref refs/remotes/origin/HEAD
  5. Creates new branch — git branch feature/update-readme development
  6. Adds git worktree — git worktree add
  /tmp/agent_workspaces/IpPlatform_...__feature_update-readme
  feature/update-readme
  7. Returns { worktree_path, branch, base_branch, head_commit, repo_url }

  ---
  5. Workspace Preamble Built

  Back in _run_generate_code, a preamble is prepended to the prompt:

  WORKSPACE READY
  working_directory : /tmp/agent_workspaces/...__feature_update-readme
  branch            : feature/update-readme
  IMPORTANT: ALL file reads/writes MUST use paths inside
  /tmp/agent_workspaces/...
  ALL git commands must cd /tmp/agent_workspaces/...

  This + the user's original prompt + a suffix (instructing Claude to
  commit and call create_pr) becomes the final prompt string.

  ---
  6. _invoke_claude → _invoke_claude_sdk

  _invoke_claude(prompt, allowed_tools=["Read","Write","Edit","Bash"],
  args, agent)
    └── _invoke_claude_sdk(...)   # async

  _invoke_claude_sdk resolves credentials:

  conn = self._get_llm_connection(agent)        # finds agent's LLM
  connection from DB
  api_key = decrypt_field(conn.api_key_enc)     # decrypts API key
  base_url = conn.base_url                       # e.g.
  http://litellm:4000/v1

  git_pat = _get_pat(agent, "azure_devops")     # same ADO PAT as Phase 0

  sdk_env = {
      "ANTHROPIC_API_KEY": api_key,             # LiteLLM proxy key
      "ANTHROPIC_BASE_URL": base_url,           # routes to LiteLLM →
  Azure
      "ADO_PAT": git_pat,                       # for git clone/push
  inside Claude's Bash
      "GIT_ADO_PAT": git_pat,
  }

  ---
  7. ThreadPoolExecutor + ProactorEventLoop

  Because uvicorn runs on SelectorEventLoop (Windows) which cannot spawn
  subprocesses, the SDK must run in a dedicated thread with its own event
  loop:

  def _run_sdk_in_thread():
      async def _collect():
          options = ClaudeCodeOptions(
              allowed_tools=["Read", "Write", "Edit", "Bash"],
              cwd="/tmp/agent_workspaces/...__feature_update-readme",
              max_turns=30,
              permission_mode="bypassPermissions",   # no permission
  prompts
              env=sdk_env,
          )
          async for message in sdk_query(prompt=full_prompt,
  options=options):
              # ... collect output

      # Windows: must use ProactorEventLoop for subprocess support
      loop = asyncio.ProactorEventLoop()
      asyncio.set_event_loop(loop)
      return loop.run_until_complete(_collect())

  with ThreadPoolExecutor(max_workers=1) as pool:
      output_text, ok, error =
  pool.submit(_run_sdk_in_thread).result(timeout=600)

  sdk_query (claude_code_sdk.query) spawns the Claude Code CLI as a child
  process.

  ---
  8. Claude Code CLI Executes

  The CLI receives:
  - The full prompt (preamble + user task + suffix)
  - ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL → all LLM calls route through
   LiteLLM proxy
  - cwd set to the worktree → every relative file path is inside the
  isolated clone
  - permission_mode="bypassPermissions" → no interactive prompts

  Claude Code then autonomously:
  1. Read — reads README.md from the worktree
  2. Write / Edit — updates README.md
  3. Bash — cd <worktree>; git add README.md; git commit -m "..."; git
  push origin feature/update-readme --push-option=...

  Git push authenticates using ADO_PAT in the subprocess environment.

  ---
  9. SDK Message Stream Collected

  The SDK yields three message types that _collect() parses:

  Type: AssistantMessage
  What it contains: content[TextBlock] — Claude's text;
    content[ToolUseBlock] — tool calls
  Handling: Text appended; tool name/keys logged
  ────────────────────────────────────────
  Type: UserMessage
  What it contains: Tool results fed back to Claude
  Handling: Not collected
  ────────────────────────────────────────
  Type: ResultMessage
  What it contains: result — final summary; is_error — failure flag
  Handling: Appended to output

  All text parts are joined → output_text.

  ---
  10. PR Creation Fallback

  After the SDK returns, Python checks if a PR was already created:

  if args.get("action") == "generate_code" and git_pat:
      if not any(kw in output_text.lower() for kw in ["pull request", "pr
  created", "pr #"]):
          # Claude didn't create the PR — do it in Python
          branch = args.get("branch_name", "")
          base = args.get("base_branch", "main")
          _create_pr_ado(
              organization=args["organization"],
              project=args["project"],
              repo=args["repo"],
              source_branch=branch,
              target_branch=base,
              title=f"feat: {args.get('prompt','')[:60]}",
              description=output_text[:2000],
              pat=git_pat,
          )

  ---
  11. Result Returned

  ToolResult(ok=True, result={"output": output_text, "branch": ...,
  "pr_url": ...}) is returned to the orchestrator, which streams it back
  to the frontend via SSE.

  ---
  Summary Diagram

  Frontend
    │ POST /chat/{agent_id}/message
    ▼
  AgentOrchestrator
    │ outer LLM decides → tool_call: claude_agent(generate_code, ...)
    ▼
  ClaudeAgentTool.execute()
    │
    ├─ Phase 0: GitWorkspaceTool
    │    └─ git clone → git branch → git worktree add
    │         (PAT from encrypted agent.git_connections)
    │
    ├─ Build prompt: preamble + user task + PR suffix
    │
    └─ _invoke_claude_sdk()
         ├─ Resolve LLM credentials (api_key + base_url from
  agent.llm_connection)
         ├─ Resolve git PAT
         ├─ ThreadPoolExecutor → ProactorEventLoop (Windows subprocess
  fix)
         └─ claude_code_sdk.query(prompt, ClaudeCodeOptions(cwd=worktree,
  env=...))
              │  streams messages
              ├─ AssistantMessage → collect TextBlock/ToolUseBlock
              └─ ResultMessage → collect final summary
         │
         └─ PR fallback if Claude didn't call git push / create PR

  The key insight is the two credential channels: the LLM API key
  (ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL) routes Claude's brain through
  LiteLLM, while the git PAT (ADO_PAT) is available to Claude's Bash tool
  for git operations — both injected as environment variables into the
  Claude Code subprocess via ClaudeCodeOptions.env.
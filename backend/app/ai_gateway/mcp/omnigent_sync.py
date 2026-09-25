"""Omnigent & Harness MCP Integration — Synchronizes CompassX AI Gateway MCP servers with all dev harnesses."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.ai_gateway.mcp.builtins import BUILTIN_MCP_SERVERS
from app.ai_gateway.models.mcp import MCPServer
from app.services.encryption import decrypt_field

logger = logging.getLogger(__name__)


def build_mcp_configs_from_gateway(
    db: Optional[Session] = None,
    workspace_id: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract all active MCP servers from AI Gateway (both built-in native platform tools
    and external/subprocess servers) and generate configurations tailored for all
    supported agent harnesses (Claude Code, Antigravity CLI, OpenCode, Codex, Cursor, Polly).
    """
    servers: list[MCPServer] = []

    if db is not None:
        try:
            query = db.query(MCPServer).filter(MCPServer.is_enabled == True)  # noqa: E712
            if workspace_id:
                query = query.filter(
                    (MCPServer.workspace_id == workspace_id) | (MCPServer.workspace_id.is_(None))
                )
            servers = query.all()
        except Exception as err:
            logger.warning("Could not query MCPServer from database: %s", err)
    else:
        try:
            from app.database import AccountSessionLocal
            with AccountSessionLocal() as session:
                query = session.query(MCPServer).filter(MCPServer.is_enabled == True)  # noqa: E712
                if workspace_id:
                    query = query.filter(
                        (MCPServer.workspace_id == workspace_id) | (MCPServer.workspace_id.is_(None))
                    )
                servers = query.all()
        except Exception as err:
            logger.warning("Could not query MCPServer via AccountSessionLocal: %s", err)

    mcp_universal: Dict[str, Any] = {}
    mcp_opencode_remote: Dict[str, Any] = {}
    mcp_claude: Dict[str, Any] = {}

    # 1. Populate Native Platform Built-in Tools (SQL Warehouse, Catalog, Notebooks, Dashboards)
    base_endpoint = (base_url or os.getenv("COMPASSX_BASE_URL", "")).rstrip("/")
    if not base_endpoint:
        base_endpoint = "https://135.13.180.167.nip.io"

    for b_name in BUILTIN_MCP_SERVERS.keys():
        endpoint = f"{base_endpoint}/api/v1/ai-gateway/mcp/servers/{b_name}/sse"
        mcp_entry: Dict[str, Any] = {
            "url": endpoint,
            "type": "sse",
        }
        mcp_universal[b_name] = mcp_entry
        mcp_claude[b_name] = mcp_entry
        mcp_opencode_remote[b_name] = {
            "type": "remote",
            "url": endpoint,
        }

    # 2. Populate External / Subprocess Registered Database Servers

    for s in servers:
        s_name = s.name
        s_type = str(s.server_type).lower() if s.server_type else "remote_sse"
        endpoint = s.endpoint_url
        cmd = s.command

        # Decrypt auth headers if present
        auth_headers: Dict[str, str] = {}
        if s.auth_config_enc:
            try:
                dec = decrypt_field(s.auth_config_enc)
                if dec:
                    auth_headers = json.loads(dec)
            except Exception:
                pass

        # Decrypt env vars if present
        env_vars: Dict[str, str] = {}
        if s.env_vars_enc:
            try:
                dec = decrypt_field(s.env_vars_enc)
                if dec:
                    env_vars = json.loads(dec)
            except Exception:
                pass

        if "sse" in s_type or "http" in s_type or endpoint:
            mcp_entry: Dict[str, Any] = {
                "url": endpoint,
                "type": "sse",
            }
            if auth_headers:
                mcp_entry["headers"] = auth_headers

            mcp_universal[s_name] = mcp_entry
            mcp_claude[s_name] = mcp_entry
            mcp_opencode_remote[s_name] = {
                "type": "remote",
                "url": endpoint,
            }
            if auth_headers:
                mcp_opencode_remote[s_name]["headers"] = auth_headers

        elif cmd or "subprocess" in s_type or "stdio" in s_type:
            parts = (cmd or "python").split()
            exec_cmd = parts[0]
            exec_args = parts[1:] if len(parts) > 1 else []

            mcp_entry = {
                "command": exec_cmd,
                "args": exec_args,
            }
            if env_vars:
                mcp_entry["env"] = env_vars

            mcp_universal[s_name] = mcp_entry
            mcp_claude[s_name] = mcp_entry
            mcp_opencode_remote[s_name] = {
                "command": exec_cmd,
                "args": exec_args,
            }
            if env_vars:
                mcp_opencode_remote[s_name]["env"] = env_vars

    opencode_config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": mcp_opencode_remote,
        "mcpServers": mcp_universal,
    }

    return {
        "mcpServers": mcp_universal,
        "opencode": opencode_config,
        "claude": {"mcpServers": mcp_claude},
        "universal": {"mcpServers": mcp_universal},
        "servers_count": len(mcp_universal),
    }


def sync_workspace_mcp_configs(
    workspace_dir: str,
    db: Optional[Session] = None,
    workspace_id: Optional[str] = None,
) -> bool:
    """
    Write standard MCP configuration files into a target workspace directory.
    Creates:
    - {workspace_dir}/.mcp.json
    - {workspace_dir}/mcp.json
    - {workspace_dir}/opencode.json
    - {workspace_dir}/.gemini/settings.json
    - {workspace_dir}/.cursor/mcp.json
    """
    if not workspace_dir or not os.path.exists(workspace_dir):
        return False

    try:
        configs = build_mcp_configs_from_gateway(db, workspace_id)
        universal_payload = configs.get("universal", {})
        opencode_payload = configs.get("opencode", {})

        # 1. Universal .mcp.json and mcp.json
        for fname in (".mcp.json", "mcp.json"):
            fp = os.path.join(workspace_dir, fname)
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(universal_payload, f, indent=2)

        # 2. OpenCode opencode.json
        fp_opencode = os.path.join(workspace_dir, "opencode.json")
        with open(fp_opencode, "w", encoding="utf-8") as f:
            json.dump(opencode_payload, f, indent=2)

        # 3. Antigravity settings.json & mcp_config.json
        gemini_dir = os.path.join(workspace_dir, ".gemini")
        os.makedirs(gemini_dir, exist_ok=True)
        fp_gemini = os.path.join(gemini_dir, "settings.json")
        with open(fp_gemini, "w", encoding="utf-8") as f:
            json.dump(universal_payload, f, indent=2)

        gemini_cfg_dir = os.path.join(gemini_dir, "config")
        os.makedirs(gemini_cfg_dir, exist_ok=True)
        fp_gemini_cfg = os.path.join(gemini_cfg_dir, "mcp_config.json")
        existing_cfg = {}
        if os.path.exists(fp_gemini_cfg):
            try:
                with open(fp_gemini_cfg, "r", encoding="utf-8") as f:
                    existing_cfg = json.load(f)
            except Exception:
                pass
        existing_servers = existing_cfg.get("mcpServers", {})
        for k, v in universal_payload.get("mcpServers", {}).items():
            existing_servers[k] = v
        existing_cfg["mcpServers"] = existing_servers
        with open(fp_gemini_cfg, "w", encoding="utf-8") as f:
            json.dump(existing_cfg, f, indent=2)

        # 4. Cursor mcp.json
        cursor_dir = os.path.join(workspace_dir, ".cursor")
        os.makedirs(cursor_dir, exist_ok=True)
        fp_cursor = os.path.join(cursor_dir, "mcp.json")
        with open(fp_cursor, "w", encoding="utf-8") as f:
            json.dump(universal_payload, f, indent=2)

        logger.info(
            "Synced %d AI Gateway MCP servers to workspace: %s",
            configs.get("servers_count", 0),
            workspace_dir,
        )
        return True
    except Exception as exc:
        logger.warning("Failed to sync MCP configs to workspace %s: %s", workspace_dir, exc)
        return False


def get_mcp_sync_shell_script(api_base_url: str = "") -> str:
    """
    Return a standalone shell snippet to dynamically fetch active MCP servers from
    CompassX AI Gateway and write configurations for Claude, OpenCode, Antigravity,
    and universal MCP clients inside any dev sandbox pod/container.
    """
    endpoint = api_base_url.rstrip("/") if api_base_url else "https://135.13.180.167.nip.io"
    return (
        f"python3 -c '"
        f"import json, os, urllib.request, ssl; "
        f"base_url = \"{endpoint}\"; "
        f"ctx = ssl._create_unverified_context(); "
        f"defaults = {{\n"
        f"  \"compassx_sql_warehouse\": {{\"url\": f\"{{base_url}}/api/v1/ai-gateway/mcp/servers/compassx_sql_warehouse/sse\", \"type\": \"sse\"}},\n"
        f"  \"compassx_catalog_search\": {{\"url\": f\"{{base_url}}/api/v1/ai-gateway/mcp/servers/compassx_catalog_search/sse\", \"type\": \"sse\"}},\n"
        f"  \"compassx_notebook_manager\": {{\"url\": f\"{{base_url}}/api/v1/ai-gateway/mcp/servers/compassx_notebook_manager/sse\", \"type\": \"sse\"}},\n"
        f"  \"compassx_dashboard_manager\": {{\"url\": f\"{{base_url}}/api/v1/ai-gateway/mcp/servers/compassx_dashboard_manager/sse\", \"type\": \"sse\"}},\n"
        f"  \"EAM_MCP\": {{\"url\": \"https://eam.135.13.180.167.nip.io/mcp/sse\", \"type\": \"sse\"}},\n"
        f"}};\n"
        f"mcp_uni = dict(defaults); mcp_oc = {{k: {{\"type\": \"remote\", \"url\": v[\"url\"]}} for k, v in defaults.items()}}; mcp_cl = dict(defaults)\n"
        f"api_url = f\"{{base_url}}/api/v1/ai-gateway/mcp/servers\"; "
        f"try:\n"
        f"  req = urllib.request.Request(api_url, headers={{\"User-Agent\": \"CompassX-Dev-Sandbox/1.0\"}});\n"
        f"  with urllib.request.urlopen(req, context=ctx, timeout=5) as r:\n"
        f"    servers = json.loads(r.read().decode())\n"
        f"  for s in servers:\n"
        f"    if not s.get(\"is_enabled\", True): continue\n"
        f"    name = s.get(\"name\") or \"mcp_server\"\n"
        f"    endpoint_u = s.get(\"endpoint_url\"); cmd = s.get(\"command\")\n"
        f"    if endpoint_u:\n"
        f"      mcp_uni[name] = {{\"url\": endpoint_u, \"type\": \"sse\"}}\n"
        f"      mcp_oc[name] = {{\"type\": \"remote\", \"url\": endpoint_u}}\n"
        f"      mcp_cl[name] = {{\"type\": \"sse\", \"url\": endpoint_u}}\n"
        f"    elif cmd:\n"
        f"      p = cmd.split()\n"
        f"      mcp_uni[name] = {{\"command\": p[0], \"args\": p[1:] if len(p) > 1 else []}}\n"
        f"      mcp_oc[name] = {{\"command\": p[0], \"args\": p[1:] if len(p) > 1 else []}}\n"
        f"      mcp_cl[name] = {{\"command\": p[0], \"args\": p[1:] if len(p) > 1 else []}}\n"
        f"except Exception:\n"
        f"  pass\n"
        f"uni_doc = {{\"mcpServers\": mcp_uni}}\n"
        f"oc_doc = {{\"mcp\": mcp_oc, \"mcpServers\": mcp_uni}}\n"
        f"import glob\n"
        f"for ws_dir in glob.glob(\"/workspaces/*\") + glob.glob(\"/workspaces/*/*\") + [os.getcwd()]:\n"
        f"  if os.path.isdir(ws_dir) and not os.path.basename(ws_dir).startswith(\".\"):\n"
        f"    for p in [\".mcp.json\", \"mcp.json\"]:\n"
        f"      try:\n"
        f"        with open(os.path.join(ws_dir, p), \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
        f"      except Exception: pass\n"
        f"    try:\n"
        f"      with open(os.path.join(ws_dir, \"opencode.json\"), \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
        f"    except Exception: pass\n"
        f"    g_dir = os.path.join(ws_dir, \".gemini\")\n"
        f"    os.makedirs(g_dir, exist_ok=True)\n"
        f"    try:\n"
        f"      with open(os.path.join(g_dir, \"settings.json\"), \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
        f"    except Exception: pass\n"
        f"os.makedirs(\"/root/.config/opencode\", exist_ok=True); os.makedirs(\"/root/.opencode\", exist_ok=True)\n"
        f"with open(\"/root/.config/opencode/opencode.json\", \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
        f"with open(\"/root/.opencode/opencode.json\", \"w\") as f: json.dump(oc_doc, f, indent=2)\n"
        f"os.makedirs(\"/workspaces/.shared_auth/.gemini/antigravity-cli\", exist_ok=True); os.makedirs(\"/root/.gemini/antigravity-cli\", exist_ok=True)\n"
        f"with open(\"/workspaces/.shared_auth/.gemini/antigravity-cli/mcp.json\", \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
        f"with open(\"/root/.gemini/antigravity-cli/mcp.json\", \"w\") as f: json.dump(uni_doc, f, indent=2)\n"
        f"for cfg_path in glob.glob(\"/root/.omnigent/antigravity-native/*/agy-home/.gemini/config/mcp_config.json\") + [\"/root/.gemini/config/mcp_config.json\", \"/workspaces/.shared_auth/.gemini/config/mcp_config.json\"]:\n"
        f"  os.makedirs(os.path.dirname(cfg_path), exist_ok=True)\n"
        f"  existing_cfg = {{}}\n"
        f"  if os.path.exists(cfg_path):\n"
        f"    try:\n"
        f"      with open(cfg_path, \"r\") as f: existing_cfg = json.load(f)\n"
        f"    except Exception: pass\n"
        f"  existing_servers = existing_cfg.get(\"mcpServers\", {{}})\n"
        f"  for k, v in mcp_uni.items(): existing_servers[k] = v\n"
        f"  existing_cfg[\"mcpServers\"] = existing_servers\n"
        f"  with open(cfg_path, \"w\") as f: json.dump(existing_cfg, f, indent=2)\n"
        f"cl_path = \"/root/.claude.json\"; cl_data = {{}}\n"
        f"if os.path.exists(cl_path):\n"
        f"  try:\n"
        f"    with open(cl_path, \"r\") as f: cl_data = json.load(f)\n"
        f"  except Exception: pass\n"
        f"cwd = os.getcwd()\n"
        f"cl_data.setdefault(\"projects\", {{}})\n"
        f"cl_data[\"projects\"].setdefault(cwd, {{}})\n"
        f"cl_data[\"projects\"][cwd][\"mcpServers\"] = mcp_cl\n"
        f"with open(cl_path, \"w\") as f: json.dump(cl_data, f, indent=2)\n"
        f"' 2>/dev/null || true"
    )

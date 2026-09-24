"""Async Client for Remote SSE and Subprocess MCP Servers."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from typing import Any

import httpx

from app.ai_gateway.mcp.types import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPTool,
    MCPToolResult,
)

logger = logging.getLogger(__name__)


def _sync_subprocess_session(
    command: str,
    env_vars: dict[str, str],
    target_method: str,
    target_params: dict[str, Any],
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    """Execute a compliant MCP stdio session with initialize handshake and request execution."""
    full_env = {**os.environ, **env_vars}
    if sys.platform == "win32":
        if isinstance(command, str) and not command.lower().startswith("cmd.exe"):
            cmd = f'cmd.exe /c "{command}"'
        else:
            cmd = command
    else:
        cmd = command

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=full_env,
        shell=True,
    )

    stderr_lines = []

    def _send(payload: dict[str, Any]):
        line = json.dumps(payload)
        proc.stdin.write(line + "\n")
        proc.stdin.flush()

    def _read_matching(target_id: str | int | None = None, deadline: float = 30.0) -> dict[str, Any] | None:
        start = time.time()
        while time.time() - start < deadline:
            line = proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line:
                continue
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if target_id is not None:
                        if data.get("id") == target_id:
                            return data
                    else:
                        return data
                except Exception:
                    continue
        return None

    try:
        # Step 1: Initialize Handshake
        _send({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "compassx-ai-gateway", "version": "1.0.0"},
            },
        })

        init_resp = _read_matching(target_id=1, deadline=min(15.0, timeout_s))
        if not init_resp:
            try:
                proc.terminate()
                _, errs = proc.communicate(timeout=2.0)
                if errs:
                    stderr_lines.append(errs.strip())
            except Exception:
                pass
            err_details = " | ".join(stderr_lines) if stderr_lines else "No response to MCP initialize handshake"
            raise RuntimeError(f"MCP server initialize failed: {err_details}")

        # Step 2: Send notifications/initialized
        _send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        # Step 3: Send Target Request (e.g. tools/list or tools/call)
        _send({
            "jsonrpc": "2.0",
            "id": 2,
            "method": target_method,
            "params": target_params,
        })

        target_resp = _read_matching(target_id=2, deadline=timeout_s)
        if not target_resp:
            try:
                proc.terminate()
                _, errs = proc.communicate(timeout=2.0)
                if errs:
                    stderr_lines.append(errs.strip())
            except Exception:
                pass
            err_details = " | ".join(stderr_lines) if stderr_lines else f"Timeout waiting for MCP method '{target_method}' response"
            raise RuntimeError(f"MCP execution failed: {err_details}")

        return target_resp

    finally:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=1.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class MCPClient:
    """Client for querying and executing tools on external/remote MCP servers."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        auth_headers: dict[str, str] | None = None,
        command: str | None = None,
        env_vars: dict[str, str] | None = None,
        timeout_s: float = 30.0,
    ):
        self.endpoint_url = endpoint_url
        self.auth_headers = auth_headers or {}
        self.command = command
        self.env_vars = env_vars or {}
        self.timeout_s = timeout_s

    async def list_tools(self) -> list[MCPTool]:
        """Call 'tools/list' JSON-RPC method on the MCP server."""
        if self.endpoint_url:
            return await self._list_tools_http()
        elif self.command:
            return await self._list_tools_subprocess()
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Call 'tools/call' JSON-RPC method on the MCP server."""
        if self.endpoint_url:
            return await self._call_tool_http(name, arguments)
        elif self.command:
            return await self._call_tool_subprocess(name, arguments)
        return MCPToolResult(isError=True, content=[{"type": "text", "text": "No valid endpoint or command configured"}])

    async def _execute_sse_session(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a compliant MCP remote SSE session over HTTP event stream."""
        from urllib.parse import urljoin
        headers = {"Accept": "text/event-stream", **self.auth_headers}
        target_req_id = str(uuid.uuid4())

        timeout = httpx.Timeout(self.timeout_s, connect=10.0, read=None)
        async with httpx.AsyncClient(timeout=timeout, verify=False, trust_env=False) as client:
            post_endpoint = None
            sse_responses: dict[str, dict[str, Any]] = {}
            target_received = asyncio.Event()

            async def sse_listener():
                nonlocal post_endpoint
                try:
                    async with client.stream("GET", self.endpoint_url, headers=headers) as resp:
                        if resp.status_code >= 400:
                            raise RuntimeError(f"HTTP error {resp.status_code} connecting to SSE endpoint")
                        buffer = ""
                        async for chunk in resp.aiter_text():
                            buffer += chunk
                            while "\n\n" in buffer or "\r\n\r\n" in buffer:
                                delim = "\r\n\r\n" if "\r\n\r\n" in buffer else "\n\n"
                                block, buffer = buffer.split(delim, 1)
                                event_type = None
                                data_str = ""
                                for line in block.splitlines():
                                    if line.startswith("event:"):
                                        event_type = line[len("event:"):].strip()
                                    elif line.startswith("data:"):
                                        data_str = line[len("data:"):].strip()

                                if event_type == "endpoint" or ("messages" in data_str and not post_endpoint):
                                    post_endpoint = urljoin(self.endpoint_url, data_str)
                                elif event_type == "message" or data_str.startswith("{"):
                                    try:
                                        msg = json.loads(data_str)
                                        msg_id = msg.get("id")
                                        if msg_id is not None:
                                            sse_responses[str(msg_id)] = msg
                                            if str(msg_id) == target_req_id:
                                                target_received.set()
                                    except Exception:
                                        pass
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.warning("SSE stream listener warning: %s", exc)

            listener_task = asyncio.create_task(sse_listener())

            try:
                start_t = asyncio.get_event_loop().time()
                while not post_endpoint and (asyncio.get_event_loop().time() - start_t < 10.0):
                    await asyncio.sleep(0.05)

                if not post_endpoint:
                    raise RuntimeError("Failed to discover MCP message endpoint from SSE stream")

                # Step 1: Initialize Handshake
                init_id = str(uuid.uuid4())
                init_req = {
                    "jsonrpc": "2.0",
                    "id": init_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "compassx-ai-gateway", "version": "1.0.0"},
                    },
                }
                post_headers = {"Content-Type": "application/json", **self.auth_headers}
                init_resp = await client.post(post_endpoint, headers=post_headers, json=init_req)
                if init_resp.status_code >= 400:
                    raise RuntimeError(f"MCP initialize handshake failed: HTTP {init_resp.status_code} {init_resp.text}")

                # Send notifications/initialized
                await client.post(
                    post_endpoint,
                    headers=post_headers,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                )

                # Step 2: Target Request
                target_req = {
                    "jsonrpc": "2.0",
                    "id": target_req_id,
                    "method": method,
                    "params": params,
                }
                resp = await client.post(post_endpoint, headers=post_headers, json=target_req)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Target MCP request failed: HTTP {resp.status_code} {resp.text}")

                await asyncio.wait_for(target_received.wait(), timeout=self.timeout_s)
                return sse_responses[target_req_id]

            finally:
                listener_task.cancel()

    async def _list_tools_http(self) -> list[MCPTool]:
        if self.endpoint_url and ("/sse" in self.endpoint_url.lower() or "sse" in self.endpoint_url.lower()):
            try:
                data = await self._execute_sse_session("tools/list", {})
                rpc_resp = JSONRPCResponse.model_validate(data)
                if rpc_resp.error:
                    raise RuntimeError(f"MCP JSON-RPC error ({rpc_resp.error.code}): {rpc_resp.error.message}")
                tools_raw = (rpc_resp.result or {}).get("tools", [])
                return [MCPTool.model_validate(t) for t in tools_raw]
            except Exception as sse_err:
                logger.info("SSE session failed, falling back to direct POST: %s", sse_err)

        req_id = str(uuid.uuid4())
        rpc_req = JSONRPCRequest(id=req_id, method="tools/list", params={})
        headers = {"Content-Type": "application/json", **self.auth_headers}

        timeout = httpx.Timeout(self.timeout_s, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, verify=False, trust_env=False) as client:
            resp = await client.post(self.endpoint_url, headers=headers, json=rpc_req.model_dump())
            if resp.status_code >= 400:
                raise RuntimeError(f"MCP server HTTP error {resp.status_code}: {resp.text}")

            data = resp.json()
            rpc_resp = JSONRPCResponse.model_validate(data)
            if rpc_resp.error:
                raise RuntimeError(f"MCP JSON-RPC error ({rpc_resp.error.code}): {rpc_resp.error.message}")

            tools_raw = (rpc_resp.result or {}).get("tools", [])
            return [MCPTool.model_validate(t) for t in tools_raw]

    async def _call_tool_http(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if self.endpoint_url and ("/sse" in self.endpoint_url.lower() or "sse" in self.endpoint_url.lower()):
            try:
                data = await self._execute_sse_session("tools/call", {"name": name, "arguments": arguments})
                rpc_resp = JSONRPCResponse.model_validate(data)
                if rpc_resp.error:
                    return MCPToolResult(
                        isError=True,
                        content=[{"type": "text", "text": f"RPC Error {rpc_resp.error.code}: {rpc_resp.error.message}"}],
                    )
                res_dict = rpc_resp.result or {}
                return MCPToolResult.model_validate(res_dict)
            except Exception as sse_err:
                logger.info("SSE tool call failed, falling back to direct POST: %s", sse_err)

        req_id = str(uuid.uuid4())
        rpc_req = JSONRPCRequest(
            id=req_id,
            method="tools/call",
            params={"name": name, "arguments": arguments},
        )
        headers = {"Content-Type": "application/json", **self.auth_headers}

        timeout = httpx.Timeout(self.timeout_s, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, verify=False, trust_env=False) as client:
            resp = await client.post(self.endpoint_url, headers=headers, json=rpc_req.model_dump())
            if resp.status_code >= 400:
                return MCPToolResult(
                    isError=True,
                    content=[{"type": "text", "text": f"HTTP {resp.status_code}: {resp.text}"}],
                )

            data = resp.json()
            rpc_resp = JSONRPCResponse.model_validate(data)
            if rpc_resp.error:
                return MCPToolResult(
                    isError=True,
                    content=[{"type": "text", "text": f"RPC Error {rpc_resp.error.code}: {rpc_resp.error.message}"}],
                )

            res_dict = rpc_resp.result or {}
            return MCPToolResult.model_validate(res_dict)

    async def _list_tools_subprocess(self) -> list[MCPTool]:
        if not self.command:
            return []
        try:
            data = await asyncio.to_thread(
                _sync_subprocess_session,
                self.command,
                self.env_vars,
                "tools/list",
                {},
                self.timeout_s,
            )
            rpc_resp = JSONRPCResponse.model_validate(data)
            if rpc_resp.error:
                logger.error("Subprocess MCP returned JSON-RPC error: %s", rpc_resp.error.message)
                return []
            tools_raw = (rpc_resp.result or {}).get("tools", [])
            return [MCPTool.model_validate(t) for t in tools_raw]
        except Exception as e:
            logger.error("Failed to list tools from subprocess MCP: %s", e)
            return []

    async def _call_tool_subprocess(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        if not self.command:
            return MCPToolResult(isError=True, content=[{"type": "text", "text": "No command configured for subprocess MCP"}])
        try:
            data = await asyncio.to_thread(
                _sync_subprocess_session,
                self.command,
                self.env_vars,
                "tools/call",
                {"name": name, "arguments": arguments},
                self.timeout_s,
            )
            rpc_resp = JSONRPCResponse.model_validate(data)
            if rpc_resp.error:
                return MCPToolResult(
                    isError=True,
                    content=[{"type": "text", "text": f"RPC Error {rpc_resp.error.code}: {rpc_resp.error.message}"}],
                )
            res_dict = rpc_resp.result or {}
            return MCPToolResult.model_validate(res_dict)
        except Exception as e:
            return MCPToolResult(
                isError=True,
                content=[{"type": "text", "text": f"Subprocess execution error: {str(e)}"}],
            )


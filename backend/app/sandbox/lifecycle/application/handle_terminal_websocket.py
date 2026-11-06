from typing import Any, Optional

from app.sandbox.shared.support import logger


class HandleTerminalWebsocket:
    async def execute(
        self,
        service,
        websocket: Any,
        sandbox_id: str,
        cols: int = 100,
        rows: int = 30,
        working_dir: Optional[str] = None,
        command: Optional[str] = None,
        agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        import asyncio
        import json
        from starlette.websockets import WebSocketState, WebSocketDisconnect

        await websocket.accept()

        instance = service.get_sandbox(sandbox_id)
        if not instance:
            instance = service.find_active_sandbox(sandbox_id=sandbox_id, consumer_key=sandbox_id)

        if not instance:
            err_msg = f"\r\n\x1b[1;31m[ERROR] Sandbox '{sandbox_id}' not found.\x1b[0m\r\n"
            try:
                await websocket.send_text(err_msg)
                await websocket.close(code=4404, reason=f"Sandbox '{sandbox_id}' not found")
            except Exception:
                pass
            return

        driver = service._get_driver_for_mode(instance.runtime_mode)

        clean_agent = (agent or "").lower().strip()
        if not clean_agent or clean_agent in ("bash", "shell", "sh"):
            welcome_banner = (
                f"\r\n\x1b[1;35m╭──────────────────────────────────────────────────────────╮\x1b[0m\r\n"
                f"\x1b[1;35m│\x1b[0m \x1b[1;32m● Connected to Sandbox Terminal\x1b[0m                          \x1b[1;35m│\x1b[0m\r\n"
                f"\x1b[1;35m│\x1b[0m Name: \x1b[1;36m{instance.name[:25]:<25}\x1b[0m Module: \x1b[1;33m{instance.consumer_module[:15]:<15}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
                f"\x1b[1;35m│\x1b[0m ID:   \x1b[90m{instance.id[:45]:<45}\x1b[0m \x1b[1;35m│\x1b[0m\r\n"
                f"\x1b[1;35m╰──────────────────────────────────────────────────────────╯\x1b[0m\r\n\r\n"
            )
            try:
                await websocket.send_text(welcome_banner)
            except Exception:
                return

        client_stream = driver.open_terminal_stream(
            instance,
            cols=cols,
            rows=rows,
            working_dir=working_dir,
            command=command,
            agent=agent,
            session_id=session_id,
        )

        if not client_stream:
            err_msg = "\r\n\x1b[1;31m[ERROR] Failed to attach interactive terminal. Is the sandbox container/pod running?\x1b[0m\r\n"
            try:
                await websocket.send_text(err_msg)
                await websocket.close(code=1011, reason="Sandbox container not reachable")
            except Exception:
                pass
            return

        is_k8s_ws = hasattr(client_stream, "write_stdin") and hasattr(client_stream, "read_stdout")
        if is_k8s_ws:
            from kubernetes.stream.ws_client import RESIZE_CHANNEL
            stop_event = asyncio.Event()

            async def pod_to_browser():
                loop = asyncio.get_running_loop()
                try:
                    while not stop_event.is_set():
                        if websocket.client_state != WebSocketState.CONNECTED or not client_stream.is_open():
                            break
                        chunk = await loop.run_in_executor(None, client_stream.read_stdout, 0.05)
                        if chunk:
                            await websocket.send_text(chunk)
                        else:
                            err_chunk = await loop.run_in_executor(None, client_stream.read_stderr, 0.02)
                            if err_chunk:
                                await websocket.send_text(err_chunk)
                            else:
                                await asyncio.sleep(0.02)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Sandbox pod to browser pipe ended: %s", e)
                finally:
                    stop_event.set()

            async def browser_to_pod():
                try:
                    while not stop_event.is_set() and client_stream.is_open():
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break

                        raw = message.get("text")
                        if raw is not None:
                            if not raw:
                                continue
                            if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                                try:
                                    data = json.loads(raw)
                                    msg_type = data.get("type")
                                    if msg_type == "resize" or ("cols" in data and "rows" in data):
                                        c = int(data.get("cols", 80))
                                        r = int(data.get("rows", 24))
                                        client_stream.write_channel(RESIZE_CHANNEL, json.dumps({"Width": c, "Height": r}))
                                        continue
                                    elif msg_type == "ping":
                                        await websocket.send_text(json.dumps({"type": "pong"}))
                                        continue
                                except Exception:
                                    pass
                            client_stream.write_stdin(raw)
                        elif "bytes" in message:
                            raw_bytes = message["bytes"]
                            if raw_bytes:
                                client_stream.write_stdin(raw_bytes.decode("utf-8", errors="replace"))
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Browser to sandbox pod pipe ended: %s", e)
                finally:
                    stop_event.set()

            try:
                await asyncio.gather(pod_to_browser(), browser_to_pod(), return_exceptions=True)
            finally:
                try:
                    client_stream.close()
                except Exception:
                    pass
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.close()
                    except Exception:
                        pass
        else:
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()

            async def proc_to_browser():
                def _read_chunk():
                    try:
                        read_fn = getattr(client_stream.stdout, "read1", client_stream.stdout.read)
                        return read_fn(1024)
                    except Exception as ex:
                        logger.debug("Stdout read exception: %s", ex)
                        return b""

                try:
                    while not stop_event.is_set() and client_stream.poll() is None:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        data = await loop.run_in_executor(None, _read_chunk)
                        if data:
                            await websocket.send_bytes(data)
                        else:
                            if client_stream.poll() is not None:
                                break
                            await asyncio.sleep(0.02)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Sandbox subprocess stdout pipe ended: %s", e)
                finally:
                    stop_event.set()

            async def browser_to_proc():
                try:
                    while not stop_event.is_set() and client_stream.poll() is None:
                        if websocket.client_state != WebSocketState.CONNECTED:
                            break
                        message = await websocket.receive()
                        if message.get("type") == "websocket.disconnect":
                            break

                        raw = message.get("text")
                        if raw is not None:
                            if not raw:
                                continue
                            if raw.startswith('{"type":') or raw.startswith('{"cols":'):
                                try:
                                    data = json.loads(raw)
                                    if data.get("type") == "ping":
                                        await websocket.send_text(json.dumps({"type": "pong"}))
                                        continue
                                    if data.get("type") == "resize" or ("cols" in data and "rows" in data):
                                        c = int(data.get("cols", 100))
                                        r = int(data.get("rows", 30))
                                        driver.resize_terminal(instance, c, r)
                                        continue
                                except Exception:
                                    pass

                            if client_stream.stdin and not client_stream.stdin.closed:
                                client_stream.stdin.write(raw.encode("utf-8"))
                                client_stream.stdin.flush()
                        elif "bytes" in message:
                            raw_bytes = message["bytes"]
                            if raw_bytes and client_stream.stdin and not client_stream.stdin.closed:
                                client_stream.stdin.write(raw_bytes)
                                client_stream.stdin.flush()
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    logger.debug("Browser to sandbox stdin pipe ended: %s", e)
                finally:
                    stop_event.set()

            try:
                await asyncio.gather(proc_to_browser(), browser_to_proc(), return_exceptions=True)
            finally:
                try:
                    if client_stream.poll() is None:
                        client_stream.terminate()
                except Exception:
                    pass
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.close()
                    except Exception:
                        pass


def handle_terminal_websocket(service, websocket, sandbox_id, cols=100, rows=30, working_dir=None, command=None, agent=None, session_id=None):
    return HandleTerminalWebsocket().execute(
        service, websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id
    )

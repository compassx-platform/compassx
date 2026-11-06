from app.sandbox.service import sandbox_service


class SandboxTerminalWebsocket:
    async def execute(self, websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id):
        await sandbox_service.handle_terminal_websocket(
            websocket=websocket,
            sandbox_id=sandbox_id,
            cols=cols,
            rows=rows,
            working_dir=working_dir,
            command=command,
            agent=agent,
            session_id=session_id,
        )


def sandbox_terminal_websocket(websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id):
    return SandboxTerminalWebsocket().execute(
        websocket, sandbox_id, cols, rows, working_dir, command, agent, session_id
    )

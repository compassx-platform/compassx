from fastapi import Request

from app.notebooks.kernel.registry import _authorize_kernel, _proxy


class ProxyKernelRestartPost:
    async def execute(self, kernel_id: str, request: Request, guard, db):
        await _authorize_kernel(guard, db, kernel_id)
        return await _proxy("POST", f"api/kernels/{kernel_id}/restart", request)


def proxy_kernel_restart_post(kernel_id, request, guard, db):
    return ProxyKernelRestartPost().execute(kernel_id, request, guard, db)

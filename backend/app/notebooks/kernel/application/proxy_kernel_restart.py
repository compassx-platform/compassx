from fastapi import Request

from app.notebooks.kernel.registry import _authorize_kernel, _proxy


class ProxyKernelRestart:
    async def execute(self, kernel_id: str, request: Request, guard, db):
        await _authorize_kernel(guard, db, kernel_id)
        return await _proxy("PATCH", f"api/kernels/{kernel_id}", request)


def proxy_kernel_restart(kernel_id, request, guard, db):
    return ProxyKernelRestart().execute(kernel_id, request, guard, db)

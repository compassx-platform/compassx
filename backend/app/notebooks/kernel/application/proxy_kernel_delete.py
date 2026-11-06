from fastapi import Request

from app.notebooks.kernel.registry import _authorize_kernel, _proxy


class ProxyKernelDelete:
    async def execute(self, kernel_id: str, request: Request, guard, db):
        await _authorize_kernel(guard, db, kernel_id)
        return await _proxy("DELETE", f"api/kernels/{kernel_id}", request)


def proxy_kernel_delete(kernel_id, request, guard, db):
    return ProxyKernelDelete().execute(kernel_id, request, guard, db)

from fastapi import Request

from app.notebooks.kernel.registry import _proxy


class ProxyKernelspecs:
    async def execute(self, request: Request):
        return await _proxy("GET", "api/kernelspecs", request)


def proxy_kernelspecs(request):
    return ProxyKernelspecs().execute(request)

from fastapi import Request

from app.notebooks.kernel.registry import _proxy


class ProxyApiInfo:
    async def execute(self, request: Request):
        return await _proxy("GET", "api", request)


def proxy_api_info(request):
    return ProxyApiInfo().execute(request)

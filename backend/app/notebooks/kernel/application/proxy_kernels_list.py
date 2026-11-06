import json

from fastapi.responses import Response

from app.notebooks.kernel.registry import _authorize_resource, _kernel_models, _resource_id_of
from fastapi import HTTPException


class ProxyKernelsList:
    async def execute(self, guard, db):
        visible = []
        for kernel in await _kernel_models():
            try:
                _authorize_resource(guard, db, _resource_id_of(kernel))
            except HTTPException:
                continue
            visible.append(kernel)

        return Response(content=json.dumps(visible), media_type="application/json")


def proxy_kernels_list(guard, db):
    return ProxyKernelsList().execute(guard, db)

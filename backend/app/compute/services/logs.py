"""Async log streaming from K8s pods."""
import asyncio
import logging
import threading
from collections.abc import AsyncGenerator

from kubernetes.client.exceptions import ApiException

from compute.k8s_client import get_k8s_client

logger = logging.getLogger(__name__)

_PENDING_RETRY_INTERVAL = 2   # seconds between retries when pod is Pending
_PENDING_MAX_WAIT = 60        # max seconds to wait for pod to start
_SENTINEL = object()          # signals end of log stream


async def stream_pod_logs(
    pod_name: str,
    namespace: str,
    container: str | None = None,
    tail_lines: int = 100,
) -> AsyncGenerator[str, None]:
    """Stream logs from a K8s pod line by line.

    Behaviour:
    - Pending: retry every 2s for up to 60s.
    - Running: follow=True, yield each line as it arrives.
    - Succeeded/Failed: return last tail_lines then stop.
    - Pod not found: yield error message and stop.

    The blocking urllib3 log iterator runs in a daemon thread so the
    asyncio event loop is never blocked waiting for log chunks.
    """
    k8s = get_k8s_client()
    waited = 0

    # Wait for pod to leave Pending state
    while waited < _PENDING_MAX_WAIT:
        try:
            logger.debug("K8s: read_namespaced_pod namespace=%s pod=%s", namespace, pod_name)
            pod = k8s.core().read_namespaced_pod(name=pod_name, namespace=namespace)
        except ApiException as exc:
            if exc.status == 404:
                yield f"[error] Pod not found: {pod_name}"
                return
            raise

        phase = pod.status.phase if pod.status and pod.status.phase else "Unknown"

        if phase == "Pending":
            await asyncio.sleep(_PENDING_RETRY_INTERVAL)
            waited += _PENDING_RETRY_INTERVAL
            continue

        break
    else:
        yield f"[error] Pod {pod_name} still Pending after {_PENDING_MAX_WAIT}s"
        return

    # Stream logs
    kwargs: dict = {
        "name": pod_name,
        "namespace": namespace,
        "tail_lines": tail_lines,
        "_preload_content": False,
    }
    if container:
        kwargs["container"] = container

    if phase == "Running":
        kwargs["follow"] = True

    logger.debug("K8s: read_namespaced_pod_log namespace=%s pod=%s follow=%s", namespace, pod_name, phase == "Running")

    try:
        resp = k8s.core().read_namespaced_pod_log(**kwargs)
    except ApiException as exc:
        if exc.status == 404:
            yield f"[error] Pod not found: {pod_name}"
        else:
            yield f"[error] Failed to stream logs: {exc.reason}"
        return

    # Blocking urllib3 iteration runs in a thread; lines are relayed via an
    # asyncio.Queue so the event loop is never blocked between chunks.
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    def _read_lines() -> None:
        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if line:
                    asyncio.run_coroutine_threadsafe(queue.put(line), loop)
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put(f"[error] Log stream error: {exc}"), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop)

    t = threading.Thread(target=_read_lines, daemon=True)
    t.start()

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        yield item

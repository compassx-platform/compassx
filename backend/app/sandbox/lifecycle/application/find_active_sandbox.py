from typing import Optional

from app.sandbox.models import SandboxInstance
from app.sandbox.shared.support import _normalize_key, logger


class FindActiveSandbox:
    def execute(
        self,
        service,
        sandbox_id: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_module: Optional[str] = None,
    ) -> Optional[SandboxInstance]:
        norm_sb_id = _normalize_key(sandbox_id)
        norm_c_key = _normalize_key(consumer_key)

        for sb in service._instances.values():
            if norm_sb_id and (
                _normalize_key(sb.id) == norm_sb_id
                or _normalize_key(sb.labels.get("compassx.sandbox-id") if sb.labels else None) == norm_sb_id
            ):
                return sb
            if norm_c_key:
                if _normalize_key(sb.consumer_key) == norm_c_key:
                    return sb
                if sb.labels and (
                    _normalize_key(sb.labels.get("compassx.consumer_key")) == norm_c_key
                    or _normalize_key(sb.labels.get("compassx.consumer-key")) == norm_c_key
                ):
                    return sb
                if sb.metadata and _normalize_key(sb.metadata.get("app_id")) == norm_c_key:
                    return sb

        try:
            discovered = service.list_sandboxes(consumer_module=consumer_module)
            for sb in discovered:
                matched = False
                if norm_sb_id and (
                    _normalize_key(sb.id) == norm_sb_id
                    or _normalize_key(sb.labels.get("compassx.sandbox-id") if sb.labels else None) == norm_sb_id
                ):
                    matched = True
                elif norm_c_key:
                    if _normalize_key(sb.consumer_key) == norm_c_key:
                        matched = True
                    elif sb.labels and (
                        _normalize_key(sb.labels.get("compassx.consumer_key")) == norm_c_key
                        or _normalize_key(sb.labels.get("compassx.consumer-key")) == norm_c_key
                    ):
                        matched = True
                    elif sb.metadata and _normalize_key(sb.metadata.get("app_id")) == norm_c_key:
                        matched = True

                if matched:
                    target_id = sandbox_id or sb.id
                    sb.id = target_id
                    service._instances[target_id] = sb
                    return sb
        except Exception as exc:
            logger.debug("Error during sandbox lookup: %s", exc)

        return None


def find_active_sandbox(service, sandbox_id=None, consumer_key=None, consumer_module=None):
    return FindActiveSandbox().execute(service, sandbox_id, consumer_key, consumer_module)

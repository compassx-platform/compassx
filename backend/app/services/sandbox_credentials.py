"""Workspace-scoped credentials for dev sandboxes.

Model access uses one random gateway secret per workspace. The sandbox
receives that secret, and the AI gateway resolves it back to the workspace.
The real provider key stays in the gateway.

Antigravity login is a separate OAuth bundle. It is stored encrypted on the
workspace. A running sandbox that presents a new login updates the record.
A sandbox without a login receives the stored files before the agent starts.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

GATEWAY_TOKEN_PREFIX = "cx_gw_ws_"
AGENT_ANTIGRAVITY = "antigravity"
TOKEN_REL = "antigravity-cli/antigravity-oauth-token"
CREDS_REL = "oauth_creds.json"
ANTIGRAVITY_FILES = (
    TOKEN_REL,
    CREDS_REL,
    "antigravity-cli/jetski_state.pbtxt",
    "antigravity-cli/installation_id",
)
_MAX_FILE_CHARS = 256_000
_AUTH_BEGIN = "__CX_AUTH_BEGIN__"
_AUTH_END = "__CX_AUTH_END__"
_LAST_SYNC: Dict[str, float] = {}
_TOKEN_CACHE: Dict[str, str] = {}

ExecTarget = Callable[[str], str]


def hash_gateway_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_real_oauth(text: str) -> bool:
    """True when the file looks like an Antigravity OAuth token, not a placeholder."""
    if not text or not text.strip():
        return False
    if "auto-authenticated" in text:
        return False
    return "refresh_token" in text or "access_token" in text


def primary_oauth(files: Optional[Dict[str, str]]) -> str:
    files = files or {}
    for rel in (TOKEN_REL, CREDS_REL):
        text = files.get(rel) or ""
        if is_real_oauth(text):
            return text.strip()
    return ""


def sanitize_auth_files(files: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Keep only the known Antigravity files, dropping placeholders and oversized blobs."""
    clean: Dict[str, str] = {}
    for rel in ANTIGRAVITY_FILES:
        text = (files or {}).get(rel)
        if not isinstance(text, str):
            continue
        if not text.strip() or len(text) > _MAX_FILE_CHARS:
            continue
        if "auto-authenticated" in text:
            continue
        clean[rel] = text
    token = clean.get(TOKEN_REL) or clean.get(CREDS_REL)
    if token and is_real_oauth(token):
        clean.setdefault(TOKEN_REL, token)
        clean.setdefault(CREDS_REL, token)
    return clean


def plan_auth_sync(
    stored: Optional[Dict[str, str]],
    pod: Optional[Dict[str, str]],
) -> tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """Decide whether the pod login should be saved, or the saved login written into the pod.

    Returns ``(files_to_save, files_to_write)``. Either value is ``None`` when
    that direction has nothing to do. A real token already in the pod wins over
    the stored copy so a fresh login is captured. A placeholder already in the
    pod does not block the stored login.
    """
    stored_clean = sanitize_auth_files(stored)
    pod_clean = sanitize_auth_files(pod)
    pod_token = primary_oauth(pod_clean)
    stored_token = primary_oauth(stored_clean)
    if pod_token and pod_clean != stored_clean:
        return pod_clean, pod_clean
    if stored_token and not pod_token:
        return None, stored_clean
    return None, None


def parse_auth_output(output: str) -> Optional[Dict[str, str]]:
    """Parse a credential read. ``None`` means the command did not answer."""
    if _AUTH_BEGIN not in output or _AUTH_END not in output:
        return None
    body = output.split(_AUTH_BEGIN, 1)[1].split(_AUTH_END, 1)[0].strip()
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return sanitize_auth_files(parsed)


def _python_exec(script: str) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return f"python3 -c \"import base64; exec(base64.b64decode('{encoded}'))\""


def reader_command() -> str:
    rels = json.dumps(list(ANTIGRAVITY_FILES))
    script = f"""
import glob, json, os
rels = {rels}
roots = ["/root/.gemini"] + glob.glob("/root/.omnigent/antigravity-native/*/agy-home/.gemini")
found = {{}}
for root in roots:
    for rel in rels:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            data = open(path, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if not data.strip() or "auto-authenticated" in data:
            continue
        prev = found.get(rel, "")
        if ("refresh_token" in data or "access_token" in data) or not prev:
            found[rel] = data
print("{_AUTH_BEGIN}")
print(json.dumps(found))
print("{_AUTH_END}")
"""
    return _python_exec(script)


def writer_command(files: Dict[str, str]) -> str:
    payload = json.dumps(sanitize_auth_files(files))
    script = f"""
import glob, json, os
files = json.loads({payload!r})
roots = ["/root/.gemini"] + glob.glob("/root/.omnigent/antigravity-native/*/agy-home/.gemini")
for rel, text in files.items():
    if rel not in {list(ANTIGRAVITY_FILES)!r}:
        continue
    if ".." in rel or rel.startswith("/"):
        continue
    for root in roots:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
"""
    return _python_exec(script)


def gateway_base_url() -> str:
    try:
        from app.services.ingress_service import ingress_service
        mode = (ingress_service.get_active_mode() or "").lower()
    except Exception:
        mode = ""
    if mode == "kubernetes":
        from app.config import settings
        ns = getattr(settings, "K8S_NAMESPACE", "compassx")
        return f"http://compassx-backend.{ns}.svc.cluster.local:8000/api/v1/ai-gateway/v1"
    # Sandboxes join the Compose network. host.docker.internal does not reach
    # the published backend port from those containers.
    if mode == "docker" or os.getenv("COMPASSX_SANDBOX_NETWORK"):
        return os.getenv(
            "COMPASSX_GATEWAY_INTERNAL_URL",
            "http://backend:8000/api/v1/ai-gateway/v1",
        )
    return "http://host.docker.internal:8000/api/v1/ai-gateway/v1"


def get_or_create_workspace_gateway_token(workspace_id: str) -> str:
    """Return the workspace gateway secret, creating it on first use."""
    cached = _TOKEN_CACHE.get(workspace_id)
    if cached:
        return cached
    from sqlalchemy.exc import IntegrityError

    from app.agents.services.encryption import decrypt_field, encrypt_field
    from app.database import AccountSessionLocal
    from app.workspace.models import WorkspaceGatewaySecret

    with AccountSessionLocal() as db:
        row = db.query(WorkspaceGatewaySecret).filter(
            WorkspaceGatewaySecret.workspace_id == workspace_id
        ).first()
        if row is None:
            token = GATEWAY_TOKEN_PREFIX + secrets.token_urlsafe(32)
            row = WorkspaceGatewaySecret(
                workspace_id=workspace_id,
                token_enc=encrypt_field(token),
                token_hash=hash_gateway_token(token),
            )
            try:
                db.add(row)
                db.commit()
            except IntegrityError:
                db.rollback()
                row = db.query(WorkspaceGatewaySecret).filter(
                    WorkspaceGatewaySecret.workspace_id == workspace_id
                ).one()
                token = decrypt_field(row.token_enc)
        else:
            token = decrypt_field(row.token_enc)
    _TOKEN_CACHE[workspace_id] = token
    return token


def gateway_api_key_for_app(app: Any) -> str:
    """Secret injected into a sandbox. Falls back to the legacy app token if the workspace has no record store."""
    workspace_id = getattr(app, "workspace_id", None)
    app_id = getattr(app, "id", "")
    if not workspace_id:
        return f"cx_gw_app_{app_id}"
    try:
        return get_or_create_workspace_gateway_token(str(workspace_id))
    except Exception:
        logger.warning("Workspace gateway token unavailable for %s", workspace_id, exc_info=True)
        return f"cx_gw_app_{app_id}"


def workspace_id_for_gateway_token(raw_token: str) -> Optional[str]:
    """Resolve a ``cx_gw_ws_`` bearer to its workspace. Returns None when the token is unknown."""
    if not raw_token or not raw_token.startswith(GATEWAY_TOKEN_PREFIX):
        return None
    from app.database import AccountSessionLocal
    from app.workspace.models import WorkspaceGatewaySecret

    digest = hash_gateway_token(raw_token)
    with AccountSessionLocal() as db:
        row = db.query(WorkspaceGatewaySecret).filter(
            WorkspaceGatewaySecret.token_hash == digest
        ).first()
        return str(row.workspace_id) if row else None


def _load_files(workspace_id: str) -> Dict[str, str]:
    from app.agents.services.encryption import decrypt_field
    from app.database import AccountSessionLocal
    from app.workspace.models import WorkspaceAgentCredential

    with AccountSessionLocal() as db:
        row = db.query(WorkspaceAgentCredential).filter(
            WorkspaceAgentCredential.workspace_id == workspace_id,
            WorkspaceAgentCredential.agent == AGENT_ANTIGRAVITY,
        ).first()
        if row is None or not row.files_enc:
            return {}
        try:
            parsed = json.loads(decrypt_field(row.files_enc))
        except Exception:
            logger.warning("Could not read stored Antigravity login for workspace %s", workspace_id)
            return {}
    return sanitize_auth_files(parsed if isinstance(parsed, dict) else {})


def _save_files(workspace_id: str, files: Dict[str, str]) -> None:
    from app.agents.services.encryption import encrypt_field
    from app.database import AccountSessionLocal
    from app.workspace.models import WorkspaceAgentCredential

    payload = encrypt_field(json.dumps(sanitize_auth_files(files)))
    with AccountSessionLocal() as db:
        row = db.query(WorkspaceAgentCredential).filter(
            WorkspaceAgentCredential.workspace_id == workspace_id,
            WorkspaceAgentCredential.agent == AGENT_ANTIGRAVITY,
        ).first()
        if row is None:
            db.add(WorkspaceAgentCredential(
                workspace_id=workspace_id,
                agent=AGENT_ANTIGRAVITY,
                files_enc=payload,
            ))
        else:
            row.files_enc = payload
        db.commit()


def _credential_targets(app: Any) -> List[ExecTarget]:
    """Live runtimes for this app. The command port owns which stacks exist."""
    from app.services.studio.sandbox_commands import build_sandbox_commands

    return build_sandbox_commands.targets(app, timeout=20)


def sync_antigravity_for_app(app: Any, *, force: bool = False, min_interval: float = 15.0) -> None:
    """Pull a fresh Antigravity login out of this app's sandbox, or push the workspace login in."""
    workspace_id = str(getattr(app, "workspace_id", "") or "")
    if not workspace_id:
        return
    app_id = str(getattr(app, "id", "") or workspace_id)
    now = time.monotonic()
    if not force and now - _LAST_SYNC.get(app_id, 0.0) < min_interval:
        return
    _LAST_SYNC[app_id] = now
    try:
        targets = _credential_targets(app)
        if not targets:
            return
        stored = _load_files(workspace_id)
        reads: List[Optional[Dict[str, str]]] = []
        for target in targets:
            try:
                reads.append(parse_auth_output(target(reader_command())))
            except Exception:
                logger.debug("Antigravity credential read failed for %s", app_id, exc_info=True)
                reads.append(None)
        current = dict(stored)
        for pod in reads:
            if not pod:
                continue
            save, _write = plan_auth_sync(current, pod)
            if save:
                current = save
        if primary_oauth(current) and current != stored:
            _save_files(workspace_id, current)
            stored = current
            logger.info("Captured Antigravity login for workspace %s", workspace_id)
        for target, pod in zip(targets, reads):
            # A failed read is an empty pod. The stored login is still written.
            _save, write = plan_auth_sync(stored, {} if pod is None else pod)
            if not write:
                continue
            try:
                target(writer_command(write))
                logger.info("Restored Antigravity login into sandbox for app %s", app_id)
            except Exception:
                logger.debug("Antigravity credential write failed for %s", app_id, exc_info=True)
    except Exception:
        logger.warning("Antigravity credential sync failed for app %s", app_id, exc_info=True)

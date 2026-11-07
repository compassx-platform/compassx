"""Workspace gateway tokens and Antigravity login sync decisions."""
import base64

from app.services.sandbox_credentials import (
    GATEWAY_TOKEN_PREFIX,
    hash_gateway_token,
    is_real_oauth,
    parse_auth_output,
    plan_auth_sync,
    reader_command,
    sanitize_auth_files,
    writer_command,
)

TOKEN = '{"refresh_token": "rt-1", "access_token": "at-1"}'
OTHER = '{"refresh_token": "rt-2", "access_token": "at-2"}'
DUMMY = '{"access_token": "auto-authenticated-dev-cluster-token"}'


def test_placeholder_is_not_a_real_login():
    assert is_real_oauth(TOKEN)
    assert not is_real_oauth(DUMMY)
    assert not is_real_oauth("")
    assert "auto-authenticated" not in sanitize_auth_files({
        "antigravity-cli/antigravity-oauth-token": DUMMY,
    })


def test_fresh_pod_login_replaces_stored_login():
    stored = {"antigravity-cli/antigravity-oauth-token": TOKEN, "oauth_creds.json": TOKEN}
    pod = {"antigravity-cli/antigravity-oauth-token": OTHER}
    save, write = plan_auth_sync(stored, pod)
    assert save["antigravity-cli/antigravity-oauth-token"] == OTHER
    assert save["oauth_creds.json"] == OTHER
    assert write == save


def test_failed_pod_read_still_restores_the_stored_login():
    stored = {"antigravity-cli/antigravity-oauth-token": TOKEN, "oauth_creds.json": TOKEN}
    save, write = plan_auth_sync(stored, {})
    assert save is None
    assert write["antigravity-cli/antigravity-oauth-token"] == TOKEN


def test_stored_login_is_written_when_pod_has_no_real_token():
    stored = {"antigravity-cli/antigravity-oauth-token": TOKEN, "oauth_creds.json": TOKEN}
    save, write = plan_auth_sync(stored, {"antigravity-cli/antigravity-oauth-token": DUMMY})
    assert save is None
    assert write["antigravity-cli/antigravity-oauth-token"] == TOKEN


def test_matching_login_is_left_alone():
    files = {"antigravity-cli/antigravity-oauth-token": TOKEN, "oauth_creds.json": TOKEN}
    assert plan_auth_sync(files, files) == (None, None)


def test_auth_output_requires_markers():
    assert parse_auth_output("not a credential read") is None
    parsed = parse_auth_output(
        'noise\n__CX_AUTH_BEGIN__\n{"oauth_creds.json": "{\\"refresh_token\\": \\"rt\\"}"}\n__CX_AUTH_END__\n'
    )
    assert parsed["oauth_creds.json"].startswith("{")
    assert "antigravity-cli/antigravity-oauth-token" in parsed


def test_sandbox_sync_saves_a_login_and_copies_it_into_an_empty_sandbox():
    import ast
    import json
    from unittest.mock import patch

    from app.services.sandbox_credentials import sync_antigravity_for_sandbox

    store = {}
    pods = {
        "sb-a": {
            "antigravity-cli/antigravity-oauth-token": TOKEN,
            "oauth_creds.json": TOKEN,
        }
    }

    def load(workspace_id):
        return dict(store.get(workspace_id, {}))

    def save(workspace_id, files):
        store[workspace_id] = dict(files)

    def target(sandbox_id):
        def run(command):
            encoded = command.split("b64decode('", 1)[1].split("')", 1)[0]
            script = base64.b64decode(encoded).decode()
            if "json.dumps(found)" in script:
                body = json.dumps(pods.get(sandbox_id, {}))
                return f"__CX_AUTH_BEGIN__\n{body}\n__CX_AUTH_END__"
            literal = script.split("json.loads(", 1)[1].split(")\nroots", 1)[0]
            pods[sandbox_id] = json.loads(ast.literal_eval(literal))
            return ""

        return run

    with patch("app.services.sandbox_credentials._load_files", load), patch(
        "app.services.sandbox_credentials._save_files", save
    ):
        sync_antigravity_for_sandbox("ws-1", target("sb-a"), sandbox_id="sb-a", force=True)
        assert store["ws-1"]["antigravity-cli/antigravity-oauth-token"] == TOKEN
        sync_antigravity_for_sandbox("ws-1", target("sb-b"), sandbox_id="sb-b", force=True)
        assert pods["sb-b"]["antigravity-cli/antigravity-oauth-token"] == TOKEN


def test_pod_commands_are_python_and_do_not_embed_a_shell_secret_unencoded():
    reader = reader_command()
    writer = writer_command({"antigravity-cli/antigravity-oauth-token": TOKEN})
    for command in (reader, writer):
        encoded = command.split("b64decode('", 1)[1].split("')", 1)[0]
        script = base64.b64decode(encoded)
        compile(script, "<pod>", "exec")
        assert "refresh_token" not in command
    assert GATEWAY_TOKEN_PREFIX == "cx_gw_ws_"
    assert hash_gateway_token("cx_gw_ws_abc") == hash_gateway_token("cx_gw_ws_abc")
    assert hash_gateway_token("cx_gw_ws_abc") != hash_gateway_token("cx_gw_ws_abd")

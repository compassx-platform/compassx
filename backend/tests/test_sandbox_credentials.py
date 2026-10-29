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

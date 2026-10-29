"""Chat transcript merge for the shared Build Studio agent session."""

from app.services.omnigent_dev_service import OmnigentDevService


def test_merge_appends_user_turns_the_pane_has_not_echoed():
    scraped = [
        {"role": "user", "content": "add a header", "created_at": "2026-10-28T10:00:00"},
        {"role": "assistant", "content": "done", "created_at": "2026-10-28T10:00:01"},
    ]
    recorded = [
        {"role": "user", "content": "add a header", "created_at": "2026-10-28T10:00:00"},
        {"role": "user", "content": "now add a footer", "created_at": "2026-10-28T10:00:05"},
    ]

    merged = OmnigentDevService.merge_chat_turns(recorded, scraped)

    assert [item["content"] for item in merged] == ["add a header", "done", "now add a footer"]


def test_omnigent_build_id_is_not_a_dev_session():
    app = type("App", (), {"id": "app-1"})()
    service = OmnigentDevService()

    assert service._is_compassx_dev_session(app, "sess_build_app-1_abcd1234") is False
    assert service._is_compassx_dev_session(app, None) is False
    assert service._is_compassx_dev_session(app, "omnigent-session") is False


def test_merge_keeps_recorded_turns_when_the_pane_is_empty():
    recorded = [{"role": "user", "content": "rename the button", "created_at": "2026-10-28T10:00:00"}]

    merged = OmnigentDevService.merge_chat_turns(recorded, [])

    assert merged == recorded

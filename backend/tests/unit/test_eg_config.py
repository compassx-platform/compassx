import pytest

from services.enterprise_gateway import config as eg_config


@pytest.fixture()
def restore_eg_settings():
    original_eg_url = eg_config.eg_settings.EG_INTERNAL_URL
    yield
    eg_config.eg_settings.EG_INTERNAL_URL = original_eg_url


def test_internal_url_explicit_override(restore_eg_settings):
    """Explicit EG_INTERNAL_URL always wins."""
    eg_config.eg_settings.EG_INTERNAL_URL = "http://my-eg-host:9999"
    assert eg_config.eg_settings.internal_url() == "http://my-eg-host:9999"


def test_internal_url_falls_back_to_registry(restore_eg_settings):
    """Without override, registry (or fallback) is used — resolves to localhost in local-dev."""
    eg_config.eg_settings.EG_INTERNAL_URL = ""
    url = eg_config.eg_settings.internal_url()
    # Registry returns localhost:8888 for local-dev; fallback is also localhost.
    assert "enterprise-gateway" in url or "8888" in url or "localhost" in url

"""Path rules for catalog model artifacts."""
import pytest

from app.catalog.registered_models.artifacts import RegistryError, safe_artifact_relative, storage_relative


def test_empty_artifact_path_means_the_whole_run():
    assert safe_artifact_relative("") == ""
    assert safe_artifact_relative("  ") == ""


def test_relative_artifact_path_is_normalised():
    assert safe_artifact_relative("model/MLmodel") == "model/MLmodel"
    assert safe_artifact_relative("/autoencoder.pt") == "autoencoder.pt"


def test_parent_segments_are_rejected():
    with pytest.raises(RegistryError) as raised:
        safe_artifact_relative("../secret")
    assert raised.value.status == 400


def test_version_storage_path_keeps_the_artifact_name():
    assert storage_relative("turbine_autoencoder", 2, "autoencoder.pt") == (
        "models/turbine_autoencoder/versions/2/autoencoder.pt"
    )

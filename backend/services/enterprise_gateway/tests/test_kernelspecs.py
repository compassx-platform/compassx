"""Tests for kernelspec generation."""
import json

import pytest

from services.enterprise_gateway.kernelspecs import (
    PROXY_CLASS_PATH,
    build_kernelspec_configmap,
    generate_kernel_json,
)


class TestGenerateKernelJson:
    def test_spark_display_name(self):
        spec = generate_kernel_json("spark")
        assert spec["display_name"] == "Python (Spark)"

    def test_ray_display_name(self):
        spec = generate_kernel_json("ray")
        assert spec["display_name"] == "Python (Ray)"

    def test_flink_display_name(self):
        spec = generate_kernel_json("flink")
        assert spec["display_name"] == "Python (Flink)"

    def test_duckdb_display_name(self):
        spec = generate_kernel_json("duckdb")
        assert spec["display_name"] == "Python (DuckDB)"

    def test_proxy_class_name_is_full_path(self):
        for runtime in ["spark", "ray", "flink", "duckdb"]:
            spec = generate_kernel_json(runtime)
            class_name = spec["metadata"]["process_proxy"]["class_name"]
            assert class_name == PROXY_CLASS_PATH
            assert "." in class_name, "Must be full dotted path"

    def test_language_is_python(self):
        spec = generate_kernel_json("spark")
        assert spec["language"] == "python"

    def test_unknown_runtime_raises(self):
        with pytest.raises(ValueError, match="Unknown runtime"):
            generate_kernel_json("unknown_runtime")


class TestBuildKernelspecConfigmap:
    def test_has_all_four_runtimes(self):
        cm = build_kernelspec_configmap("compassx-services")
        assert "spark_python/kernel.json" in cm.data
        assert "ray_python/kernel.json" in cm.data
        assert "flink_python/kernel.json" in cm.data
        assert "duckdb_python/kernel.json" in cm.data

    def test_values_are_valid_json(self):
        cm = build_kernelspec_configmap("compassx-services")
        for key, value in cm.data.items():
            parsed = json.loads(value)
            assert "display_name" in parsed, f"{key} missing display_name"

    def test_namespace_set_correctly(self):
        cm = build_kernelspec_configmap("compassx-services")
        assert cm.metadata.namespace == "compassx-services"

    def test_configmap_name(self):
        cm = build_kernelspec_configmap("compassx-services")
        assert cm.metadata.name == "compassx-kernelspecs"

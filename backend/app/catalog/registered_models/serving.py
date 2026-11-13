"""Score records with a registered model version.

The runtime reads the contract from the artifact. Column names, scaling,
held-out inputs, and the threshold live in the checkpoint, not in this module.
"""
from __future__ import annotations

import io
import threading
from typing import Any

from app.catalog.registered_models.artifacts import RegistryError

_CACHE: dict[tuple, dict[str, Any]] = {}
_LOCK = threading.Lock()


def _storage():
    from app.catalog.storage_context import resolve_catalog_storage

    return resolve_catalog_storage


def _torch():
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RegistryError(503, "PyTorch is not available, so this model artifact cannot be scored.") from exc
    return torch, nn


def _linear_stack(nn, state: dict, prefix: str):
    layers = []
    index = 0
    while f"{prefix}.{index}.weight" in state:
        out_features, in_features = state[f"{prefix}.{index}.weight"].shape
        layers.append(nn.Linear(int(in_features), int(out_features)))
        if f"{prefix}.{index + 2}.weight" in state:
            layers.append(nn.ReLU())
            index += 2
        elif f"{prefix}.{index + 1}.weight" in state:
            index += 1
        else:
            break
    if not layers:
        raise RegistryError(400, "The artifact does not contain a reconstruction network.")
    return nn.Sequential(*layers)


def _as_name_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _mask_columns(payload: dict, features: list[str]) -> list[str]:
    for key in ("mask_columns", "score_columns", "held_out_columns"):
        names = _as_name_list(payload.get(key))
        if names:
            return names
    allowed = set(features)
    for key, value in payload.items():
        if key == "features":
            continue
        names = _as_name_list(value)
        if names and set(names) <= allowed:
            return names
    return []


def _vector(spec: Any, features: list[str], default: float) -> list[float]:
    if isinstance(spec, dict):
        return [float(spec.get(name, default) or default) for name in features]
    if isinstance(spec, (list, tuple)) and len(spec) == len(features):
        return [float(item or default) for item in spec]
    return [default for _ in features]


def _prepare(payload: dict) -> dict[str, Any]:
    torch, nn = _torch()
    state = payload.get("state_dict")
    features = _as_name_list(payload.get("features"))
    if not isinstance(state, dict) or not features:
        raise RegistryError(400, "The artifact has no feature contract and state dictionary.")
    mask_names = _mask_columns(payload, features)
    unknown = [name for name in mask_names if name not in features]
    if unknown:
        raise RegistryError(400, f"The artifact mask names unknown features: {', '.join(unknown)}.")
    model = nn.Module()
    model.encoder = _linear_stack(nn, state, "encoder")
    model.decoder = _linear_stack(nn, state, "decoder")
    model.load_state_dict(state)
    model.eval()
    threshold = payload.get("threshold")
    return {
        "model": model,
        "torch": torch,
        "features": features,
        "mask_index": [features.index(name) for name in mask_names],
        "mean": _vector(payload.get("mu") or payload.get("mean"), features, 0.0),
        "std": [value if value else 1.0 for value in _vector(payload.get("sigma") or payload.get("std"), features, 1.0)],
        "threshold": float(threshold) if threshold not in (None, "") else None,
    }


def _load_checkpoint(blob: bytes) -> dict[str, Any]:
    torch, _nn = _torch()
    try:
        payload = torch.load(io.BytesIO(blob), map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(io.BytesIO(blob), map_location="cpu")
    if not isinstance(payload, dict):
        raise RegistryError(400, "The model artifact is not a scoring checkpoint.")
    return _prepare(payload)


async def _artifact_bytes(db, catalog_name: str, schema_name: str, relative: str) -> bytes:
    ctx = _storage()(db, catalog_name, schema_name)
    if ctx is None:
        raise RegistryError(400, f"Schema '{catalog_name}.{schema_name}' has no storage backend.")
    return await ctx.backend.read_bytes(ctx.rel_path(relative))


def _choose_file(files: list[str]) -> str:
    runnable = [path for path in files if path.endswith((".pt", ".pth"))]
    if not runnable:
        raise RegistryError(400, "This model version has no runnable artifact.")
    return runnable[0]


def score_records(prepared: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features = prepared["features"]
    matrix = []
    for index, record in enumerate(records):
        row = []
        for name in features:
            if name not in record or record[name] is None or record[name] == "":
                raise RegistryError(400, f"Record {index} is missing feature '{name}'.")
            try:
                row.append(float(record[name]))
            except (TypeError, ValueError) as exc:
                raise RegistryError(400, f"Record {index} feature '{name}' is not numeric.") from exc
        matrix.append(row)

    torch = prepared["torch"]
    mean_list = prepared["mean"]
    std_list = prepared["std"]
    mean = torch.tensor(mean_list, dtype=torch.float32)
    std = torch.tensor(std_list, dtype=torch.float32)
    values = (torch.tensor(matrix, dtype=torch.float32) - mean) / std
    mask_index = list(prepared["mask_index"])
    scored_index = mask_index or list(range(len(features)))
    mask = torch.tensor(mask_index, dtype=torch.long)
    scored = torch.tensor(scored_index, dtype=torch.long)
    with torch.no_grad():
        hidden = values.clone()
        if mask.numel():
            hidden[:, mask] = 0
        reconstructed = prepared["model"].decoder(prepared["model"].encoder(hidden))
        per_feature = (reconstructed.index_select(1, scored) - values.index_select(1, scored)) ** 2
        error = per_feature.mean(dim=1)
    threshold = prepared["threshold"]
    reconstructed_rows = reconstructed.tolist()
    per_rows = per_feature.tolist()
    predictions = []
    for row_index, value in enumerate(error.tolist()):
        score = (value / threshold) if threshold else value
        total = sum(per_rows[row_index]) or 1.0
        contributions = []
        for slot, feature_index in enumerate(scored_index):
            scale = std_list[feature_index] or 1.0
            squared = float(per_rows[row_index][slot])
            contributions.append(
                {
                    "feature": features[feature_index],
                    "squared_error": squared,
                    "share": squared / total,
                    "actual": float(matrix[row_index][feature_index]),
                    "expected": float(reconstructed_rows[row_index][feature_index]) * scale + float(mean_list[feature_index]),
                }
            )
        signals = []
        for feature_index, name in enumerate(features):
            scale = std_list[feature_index] or 1.0
            actual = float(matrix[row_index][feature_index])
            signals.append(
                {
                    "feature": name,
                    "value": actual,
                    "z": (actual - float(mean_list[feature_index])) / scale,
                }
            )
        predictions.append(
            {
                "reconstruction_error": value,
                "anomaly_score": score,
                "above_threshold": bool(threshold is not None and value >= threshold),
                "contributions": contributions,
                "signals": signals,
            }
        )
    return predictions


async def invoke_model(db, model, version, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    artifact = _choose_file(list(version.files or []))
    cache_key = (model.catalog_name, model.schema_name, model.name, version.version, artifact)
    with _LOCK:
        prepared = _CACHE.get(cache_key)
    if prepared is None:
        blob = await _artifact_bytes(db, model.catalog_name, model.schema_name, artifact)
        prepared = _load_checkpoint(blob)
        with _LOCK:
            _CACHE[cache_key] = prepared
    with _LOCK:
        return score_records(prepared, records)

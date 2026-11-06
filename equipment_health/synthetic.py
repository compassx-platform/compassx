"""Synthetic deviations injected into real normal windows.

Signs inside a coupling group are randomized. The autoencoder learned normal
correlation, not the direction a fault pushes related sensors.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from equipment_health.residuals import ResidualScale, window_residual

SHAPES = ("ramp", "step", "intermittent", "variance", "stuck")


def shape_offset(length: int, shape: str, magnitude: float, rng: np.random.Generator) -> np.ndarray | None:
    """Time pattern added to one feature. Stuck values are applied separately."""
    position = np.linspace(0.0, 1.0, length)
    if shape == "ramp":
        return magnitude * position
    if shape == "step":
        return magnitude * (position >= 0.5)
    if shape == "intermittent":
        return magnitude * (rng.random(length) < 0.3)
    if shape == "variance":
        return rng.normal(0.0, abs(magnitude), size=length)
    if shape == "stuck":
        return None
    raise ValueError(f"Unknown shape: {shape}")


def apply_injection(
    window: np.ndarray,
    features: list[int],
    signs: np.ndarray,
    shape: str,
    magnitudes: np.ndarray,
    rng: np.random.Generator,
    low: np.ndarray,
    high: np.ndarray,
) -> np.ndarray:
    """Add one deviation and keep every feature inside its observed range."""
    updated = np.array(window, dtype=np.float64, copy=True)
    offset = shape_offset(window.shape[0], shape, 1.0, rng)
    for feature, sign, magnitude in zip(features, signs, magnitudes):
        if shape == "stuck":
            updated[:, feature] = window[0, feature]
            continue
        updated[:, feature] = window[:, feature] + sign * magnitude * offset
    return np.clip(updated, low, high)


@dataclass
class SyntheticSet:
    windows: np.ndarray
    directions: np.ndarray
    severities: np.ndarray
    targets: np.ndarray
    shapes: list[str]


def generate_synthetic(
    normal_windows: np.ndarray,
    reconstruct,
    scale: ResidualScale,
    groups: list[list[int]],
    count: int,
    rng: np.random.Generator,
    min_severity: float = 2.0,
    max_features: int = 3,
    magnitude_range: tuple[float, float] = (3.0, 10.0),
) -> SyntheticSet:
    """Inject detectable deviations and keep their residual direction."""
    windows = np.asarray(normal_windows, dtype=np.float64)
    unit = scale.injection_unit()
    chosen_windows = []
    directions = []
    severities = []
    targets = []
    shapes: list[str] = []
    attempts = 0
    limit = max(count * 30, count)
    features = windows.shape[-1]
    usable_groups = [group for group in groups if group] or [list(range(features))]

    while len(chosen_windows) < count and attempts < limit:
        attempts += 1
        source = windows[int(rng.integers(0, windows.shape[0]))]
        group = usable_groups[int(rng.integers(0, len(usable_groups)))]
        width = int(rng.integers(1, min(max_features, len(group)) + 1))
        picked = list(rng.choice(group, size=width, replace=False))
        signs = rng.choice(np.array([-1.0, 1.0]), size=width)
        shape = SHAPES[int(rng.integers(0, len(SHAPES)))]
        magnitudes = unit[picked] * rng.uniform(magnitude_range[0], magnitude_range[1], size=width)
        injected = apply_injection(
            source,
            picked,
            signs,
            shape,
            magnitudes,
            rng,
            scale.feature_min,
            scale.feature_max,
        )
        residual = window_residual(injected[None, ...], reconstruct(injected[None, ...]))[0]
        _scored, direction, severity = scale.transform(residual[None, ...])
        if float(severity[0]) < min_severity:
            continue
        target = np.zeros(features, dtype=np.float64)
        target[picked] = signs * magnitudes
        target = target / max(np.linalg.norm(target), 1e-8)
        chosen_windows.append(injected)
        directions.append(direction[0])
        severities.append(float(severity[0]))
        targets.append(target)
        shapes.append(shape)

    if len(chosen_windows) < count:
        raise RuntimeError(
            f"Only {len(chosen_windows)} of {count} synthetic faults were detectable. "
            "Lower min_severity or widen magnitude_range."
        )
    return SyntheticSet(
        windows=np.stack(chosen_windows),
        directions=np.stack(directions),
        severities=np.asarray(severities, dtype=np.float64),
        targets=np.stack(targets),
        shapes=shapes,
    )

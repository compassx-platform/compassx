"""Coupling groups from how the autoencoder fills in a perturbed sensor."""
from __future__ import annotations

from typing import Callable

import numpy as np

Reconstructor = Callable[[np.ndarray], np.ndarray]


def reconstruction_sensitivity(
    reconstruct: Reconstructor,
    windows: np.ndarray,
    scales: np.ndarray,
) -> np.ndarray:
    """Row i is the mean absolute reconstruction change after perturbing feature i.

    The values are correlations the autoencoder learned on normal data. They
    say which sensors move together. They do not say how a fault propagates.
    """
    windows = np.asarray(windows, dtype=np.float64)
    scales = np.asarray(scales, dtype=np.float64)
    base = np.asarray(reconstruct(windows), dtype=np.float64)
    features = windows.shape[-1]
    sensitivity = np.zeros((features, features), dtype=np.float64)
    for index in range(features):
        perturbed = np.array(windows, copy=True)
        perturbed[..., index] = perturbed[..., index] + scales[index]
        delta = np.asarray(reconstruct(perturbed), dtype=np.float64) - base
        sensitivity[index] = np.mean(np.abs(delta), axis=tuple(range(delta.ndim - 1)))
    return sensitivity


def groups_from_sensitivity(sensitivity: np.ndarray, threshold: float = 0.3) -> list[list[int]]:
    """Connected features whose reconstruction responds to each other."""
    sensitivity = np.asarray(sensitivity, dtype=np.float64)
    features = sensitivity.shape[0]
    row_scale = np.maximum(np.diag(sensitivity), sensitivity.max(axis=1))
    row_scale = np.maximum(row_scale, 1e-8)
    relative = sensitivity / row_scale[:, None]
    affinity = np.maximum(relative, relative.T)
    np.fill_diagonal(affinity, 0.0)

    parent = list(range(features))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for left in range(features):
        for right in range(left + 1, features):
            if affinity[left, right] >= threshold:
                parent[find(left)] = find(right)

    grouped: dict[int, list[int]] = {}
    for index in range(features):
        grouped.setdefault(find(index), []).append(index)
    return [sorted(members) for members in grouped.values()]

"""Per-feature residuals, split into direction and severity."""
from __future__ import annotations

import numpy as np


class ResidualScale:
    """Z-score each feature's signed residual against normal error spread."""

    def __init__(self):
        self.mean = None
        self.std = None
        self.feature_std = None
        self.feature_min = None
        self.feature_max = None

    def fit(self, residuals: np.ndarray, windows: np.ndarray) -> "ResidualScale":
        residuals = np.asarray(residuals, dtype=np.float64)
        windows = np.asarray(windows, dtype=np.float64)
        self.mean = residuals.mean(axis=0)
        spread = residuals.std(axis=0)
        feature_std = windows.reshape(-1, windows.shape[-1]).std(axis=0)
        # A near-perfect reconstruction has no error spread. Fall back to the
        # feature's own scale so later injections stay in comparable units.
        self.std = np.maximum(spread, np.maximum(1e-3 * feature_std, 1e-6))
        self.feature_std = np.maximum(feature_std, 1e-6)
        flat = windows.reshape(-1, windows.shape[-1])
        self.feature_min = flat.min(axis=0)
        self.feature_max = flat.max(axis=0)
        return self

    def injection_unit(self) -> np.ndarray:
        """Scale used to size a synthetic deviation."""
        return np.maximum(self.std, 1e-3 * self.feature_std)

    def transform(self, residuals: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        residuals = np.asarray(residuals, dtype=np.float64)
        scored = (residuals - self.mean) / self.std
        severity = np.linalg.norm(scored, axis=-1)
        direction = scored / np.maximum(severity[:, None], 1e-8)
        return scored, direction, severity


def window_residual(original: np.ndarray, reconstructed: np.ndarray) -> np.ndarray:
    """Signed per-feature residual.

    The size is the root-mean-square error, so a variance increase is visible.
    The sign is the direction of the mean shift.
    """
    delta = np.asarray(original, dtype=np.float64) - np.asarray(reconstructed, dtype=np.float64)
    signed = np.sign(delta.mean(axis=1))
    signed = np.where(signed == 0.0, 1.0, signed)
    energy = np.sqrt(np.mean(delta ** 2, axis=1))
    return signed * energy

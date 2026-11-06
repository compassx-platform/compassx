"""Fit a health map from normal windows and read it back on new windows."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from equipment_health.autoencoder import AutoencoderModel
from equipment_health.coupling import groups_from_sensitivity, reconstruction_sensitivity
from equipment_health.embedding import EmbeddingModel
from equipment_health.prototypes import PrototypeLibrary
from equipment_health.realism import realism_gap
from equipment_health.residuals import ResidualScale, window_residual
from equipment_health.synthetic import SyntheticSet, generate_synthetic


@dataclass
class HealthPoint:
    direction: np.ndarray
    severity: np.ndarray
    embedding: np.ndarray
    xy: np.ndarray


class HealthMap:
    """Normal autoencoder, coupling groups, synthetic deviations, and an embedding.

    The two plotted axes are a projection of a 16 to 64 dimensional embedding.
    Severity is kept separate so a stronger version of the same deviation stays
    on the same direction.
    """

    def __init__(self, embedding_dim: int = 32, latent: int = 16):
        self.embedding_dim = embedding_dim
        self.latent = latent
        self.autoencoder: AutoencoderModel | None = None
        self.scale = ResidualScale()
        self.groups: list[list[int]] = []
        self.sensitivity: np.ndarray | None = None
        self.embedding: EmbeddingModel | None = None
        self.synthetic: SyntheticSet | None = None
        self.prototypes = PrototypeLibrary()

    def fit(
        self,
        normal_windows: np.ndarray,
        synthetic_count: int = 256,
        ae_epochs: int = 25,
        embedding_epochs: int = 30,
        seed: int = 0,
        min_severity: float = 2.0,
    ) -> "HealthMap":
        windows = np.asarray(normal_windows, dtype=np.float64)
        _count, time, features = windows.shape
        self.autoencoder = AutoencoderModel(features, time, latent=self.latent)
        self.autoencoder.fit(windows, epochs=ae_epochs, seed=seed)
        normal_residual = window_residual(windows, self.autoencoder.reconstruct(windows))
        self.scale.fit(normal_residual, windows)
        self.sensitivity = reconstruction_sensitivity(
            self.autoencoder.reconstruct,
            windows[: min(64, len(windows))],
            self.scale.injection_unit(),
        )
        self.groups = groups_from_sensitivity(self.sensitivity)
        rng = np.random.default_rng(seed)
        self.synthetic = generate_synthetic(
            windows,
            self.autoencoder.reconstruct,
            self.scale,
            self.groups,
            synthetic_count,
            rng,
            min_severity=min_severity,
        )
        self.embedding = EmbeddingModel(features, embedding_dim=self.embedding_dim)
        self.embedding.fit(
            self.synthetic.directions,
            self.synthetic.targets,
            epochs=embedding_epochs,
            seed=seed,
        )
        return self

    def transform(self, windows: np.ndarray) -> HealthPoint:
        if self.autoencoder is None or self.embedding is None:
            raise RuntimeError("Fit the health map before transforming windows.")
        residual = window_residual(windows, self.autoencoder.reconstruct(windows))
        _scored, direction, severity = self.scale.transform(residual)
        embedding = self.embedding.encode(direction)
        xy = self.embedding.project(embedding)
        return HealthPoint(direction=direction, severity=severity, embedding=embedding, xy=xy)

    def compare_real_faults(self, fault_windows: np.ndarray, holdout: int = 32) -> dict[str, float]:
        """See whether real fault residuals land inside the synthetic set."""
        if self.synthetic is None:
            raise RuntimeError("Fit the health map before comparing faults.")
        observed = self.transform(fault_windows)
        return realism_gap(observed.direction, self.synthetic.directions, holdout=holdout)

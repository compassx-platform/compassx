import numpy as np

from equipment_health.coupling import groups_from_sensitivity, reconstruction_sensitivity
from equipment_health.pipeline import HealthMap
from equipment_health.prototypes import PrototypeLibrary
from equipment_health.residuals import ResidualScale, window_residual
from equipment_health.synthetic import apply_injection, generate_synthetic, shape_offset


def _coupled_reconstruct(windows):
    restored = np.array(windows, copy=True)
    restored[..., 1] = 0.2 * windows[..., 1] + 0.8 * windows[..., 0]
    restored[..., 3] = 0.2 * windows[..., 3] + 0.8 * windows[..., 2]
    return restored


def test_coupling_groups_follow_normal_reconstruction():
    rng = np.random.default_rng(0)
    windows = rng.normal(size=(40, 8, 4))
    sensitivity = reconstruction_sensitivity(_coupled_reconstruct, windows, np.ones(4))
    groups = groups_from_sensitivity(sensitivity, threshold=0.3)
    assert sorted(tuple(group) for group in groups) == [(0, 1), (2, 3)]


def test_shapes_cover_ramp_step_and_stuck():
    rng = np.random.default_rng(1)
    ramp = shape_offset(4, "ramp", 2.0, rng)
    step = shape_offset(4, "step", 2.0, rng)
    assert ramp[0] == 0.0
    assert ramp[-1] == 2.0
    assert step[0] == 0.0
    assert step[-1] == 2.0
    window = np.ones((4, 2))
    stuck = apply_injection(window, [0], np.array([-1.0]), "stuck", np.array([3.0]), rng, np.zeros(2), np.full(2, 5.0))
    assert np.all(stuck[:, 0] == 1.0)


def test_undetectable_injection_is_dropped():
    rng = np.random.default_rng(2)
    windows = rng.normal(size=(30, 6, 3))

    def reconstruct(batch):
        return np.zeros_like(batch)

    residual = window_residual(windows, reconstruct(windows))
    scale = ResidualScale().fit(residual, windows)
    generated = generate_synthetic(
        windows,
        reconstruct,
        scale,
        [[0], [1], [2]],
        count=8,
        rng=rng,
        min_severity=1.0,
        magnitude_range=(4.0, 6.0),
    )
    assert generated.windows.shape[0] == 8
    assert np.all(generated.severities >= 1.0)
    assert np.allclose(np.linalg.norm(generated.directions, axis=1), 1.0)


def test_health_map_projects_a_deviation_away_from_normal():
    rng = np.random.default_rng(3)
    load = rng.normal(size=(80, 12, 1))
    noise = rng.normal(scale=0.05, size=(80, 12, 4))
    windows = np.concatenate(
        [
            load,
            0.85 * load,
            rng.normal(size=(80, 12, 1)),
            0.85 * noise[:, :, 2:3],
        ],
        axis=-1,
    )
    windows = windows + noise
    health = HealthMap(embedding_dim=16, latent=8)
    health.fit(windows, synthetic_count=48, ae_epochs=8, embedding_epochs=6, seed=3, min_severity=1.0)
    normal = health.transform(windows[:10])
    fault = np.array(windows[:10], copy=True)
    fault[:, :, 0] += 4.0
    shifted = health.transform(fault)
    assert normal.xy.shape == (10, 2)
    assert shifted.embedding.shape[1] == 16
    assert shifted.severity.mean() > normal.severity.mean()


def test_real_faults_far_from_synthetics_score_a_larger_gap():
    rng = np.random.default_rng(4)
    windows = rng.normal(size=(40, 8, 4))
    health = HealthMap(embedding_dim=16, latent=4)
    health.fit(windows, synthetic_count=40, ae_epochs=2, embedding_epochs=2, seed=4, min_severity=0.5)
    near = health.synthetic.windows[:8]
    far = np.array(windows[:8], copy=True)
    far += rng.normal(scale=25.0, size=far.shape)
    near_gap = health.compare_real_faults(near, holdout=8)
    far_gap = health.compare_real_faults(far, holdout=8)
    assert near_gap["ratio"] > 0
    assert far_gap["real_to_synthetic"] > near_gap["real_to_synthetic"]


def test_unknown_embedding_stays_outside_known_prototypes():
    library = PrototypeLibrary()
    library.add("bearing-temperature", np.array([1.0, 0.0, 0.0]))
    name, _distance = library.match(np.array([1.0, 0.05, 0.0]), unknown_distance=0.2)
    unknown, distance = library.match(np.array([0.0, 0.0, 1.0]), unknown_distance=0.2)
    assert name == "bearing-temperature"
    assert unknown == "unknown"
    assert distance > 0.2

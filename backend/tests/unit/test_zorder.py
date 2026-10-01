import numpy as np
import pandas as pd
import pytest

from services.compassx_sql.zorder import (
    normalize_to_uint32,
    interleave_bits_2d,
    interleave_bits_nd,
    z_order_dataframe,
)


def test_normalize_to_uint32_numeric():
    s = pd.Series([10.0, 20.0, 30.0, 40.0])
    u = normalize_to_uint32(s)
    assert len(u) == 4
    assert u.dtype == np.uint32
    assert u[0] == 0
    assert u[-1] == 2**32 - 1
    assert u[1] < u[2]


def test_normalize_to_uint32_constant_and_empty():
    s_const = pd.Series([5.0, 5.0, 5.0])
    u_const = normalize_to_uint32(s_const)
    assert np.all(u_const == 0)

    s_empty = pd.Series([], dtype="float64")
    u_empty = normalize_to_uint32(s_empty)
    assert len(u_empty) == 0


def test_normalize_to_uint32_with_nulls():
    s = pd.Series([10.0, None, 50.0, np.nan])
    u = normalize_to_uint32(s)
    assert len(u) == 4
    assert u[0] == 0
    assert u[2] == 2**32 - 1


def test_normalize_to_uint32_datetime():
    s = pd.Series(pd.to_datetime(["2026-01-01", "2026-06-01", "2026-12-31"]))
    u = normalize_to_uint32(s)
    assert len(u) == 3
    assert u[0] == 0
    assert u[-1] == 2**32 - 1
    assert u[0] < u[1] < u[2]


def test_normalize_to_uint32_boolean():
    s = pd.Series([False, True, False, True])
    u = normalize_to_uint32(s)
    assert u[0] == 0
    assert u[1] == 2**32 - 1
    assert u[2] == 0


def test_normalize_to_uint32_strings():
    s = pd.Series(["alpha", "beta", "gamma", "delta"])
    u = normalize_to_uint32(s)
    assert len(u) == 4
    # alpha is lowest rank, gamma is highest rank
    assert u[0] == 0
    assert u[2] == 2**32 - 1


def test_interleave_bits_2d():
    x = np.array([0, 1, 0, 1], dtype=np.uint32)
    y = np.array([0, 0, 1, 1], dtype=np.uint32)
    z = interleave_bits_2d(x, y)
    assert len(z) == 4
    assert z[0] == 0  # (0, 0) -> 0b00 = 0
    assert z[1] == 1  # (1, 0) -> 0b01 = 1
    assert z[2] == 2  # (0, 1) -> 0b10 = 2
    assert z[3] == 3  # (1, 1) -> 0b11 = 3


def test_interleave_bits_nd_3d():
    x = np.array([0, 2**32 - 1], dtype=np.uint32)
    y = np.array([0, 2**32 - 1], dtype=np.uint32)
    z_arr = np.array([0, 2**32 - 1], dtype=np.uint32)
    keys = interleave_bits_nd([x, y, z_arr])
    assert len(keys) == 2
    assert keys[0] == 0
    assert keys[1] > 0


def test_z_order_dataframe_2d():
    # Grid of (x, y) coordinates
    df = pd.DataFrame({
        "x": [100.0, 0.0, 100.0, 0.0],
        "y": [100.0, 100.0, 0.0, 0.0],
        "label": ["top_right", "top_left", "bottom_right", "bottom_left"],
    })
    sorted_df = z_order_dataframe(df, ["x", "y"])
    # Morton order for (0,0), (1,0), (0,1), (1,1) is bottom_left, bottom_right, top_left, top_right
    expected_order = ["bottom_left", "bottom_right", "top_left", "top_right"]
    assert list(sorted_df["label"]) == expected_order


def test_z_order_dataframe_mixed_types():
    df = pd.DataFrame({
        "ts": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"]),
        "region": ["US", "US", "EU", "EU"],
        "metric": [10, 20, 30, 40],
    })
    sorted_df = z_order_dataframe(df, ["region", "ts"])
    assert len(sorted_df) == 4
    assert set(sorted_df["metric"]) == {10, 20, 30, 40}


def test_z_order_dataframe_single_and_empty():
    df = pd.DataFrame({"a": [3, 1, 2]})
    s1 = z_order_dataframe(df, ["a"])
    assert list(s1["a"]) == [1, 2, 3]

    s2 = z_order_dataframe(df, [])
    assert list(s2["a"]) == [3, 1, 2]

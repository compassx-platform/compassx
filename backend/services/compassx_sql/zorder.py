"""Z-Order (Morton Space-Filling Curve) Clustering Utility.

Maps multi-dimensional data points to 1D Morton space-filling curves to optimize
Parquet row-group data layout for multi-column predicate pushdown and skipping.
"""
from __future__ import annotations

from typing import Sequence
import numpy as np
import pandas as pd


def normalize_to_uint32(series: pd.Series) -> np.ndarray:
    """Normalize any pandas Series (numeric, datetime, boolean, string) to a uint32 array."""
    if len(series) == 0:
        return np.empty(0, dtype=np.uint32)

    # Handle booleans
    if pd.api.types.is_bool_dtype(series):
        arr = series.fillna(False).astype(np.uint32).to_numpy()
        return arr * (2**32 - 1)

    # Handle datetimes
    if pd.api.types.is_datetime64_any_dtype(series):
        ts = pd.to_datetime(series).astype("int64").to_numpy() // 10**9  # unix epoch seconds
        valid = series.notna().to_numpy()
        if not np.any(valid):
            return np.zeros(len(series), dtype=np.uint32)
        min_v = ts[valid].min()
        max_v = ts[valid].max()
        if min_v == max_v:
            return np.zeros(len(series), dtype=np.uint32)
        norm = np.clip((ts - min_v) / (max_v - min_v), 0.0, 1.0)
        norm[~valid] = 0.0
        return (norm * (2**32 - 1)).astype(np.uint32)

    # Handle numerics
    if pd.api.types.is_numeric_dtype(series):
        vals = pd.to_numeric(series, errors="coerce").to_numpy(dtype=np.float64)
        valid = ~np.isnan(vals)
        if not np.any(valid):
            return np.zeros(len(series), dtype=np.uint32)
        min_v = vals[valid].min()
        max_v = vals[valid].max()
        if min_v == max_v:
            return np.zeros(len(series), dtype=np.uint32)
        norm = np.clip((vals - min_v) / (max_v - min_v), 0.0, 1.0)
        norm[~valid] = 0.0
        return (norm * (2**32 - 1)).astype(np.uint32)

    # Handle strings / categoricals / objects (rank-based normalization)
    ranks = series.astype(str).rank(method="dense", na_option="bottom").to_numpy()
    min_v = ranks.min()
    max_v = ranks.max()
    if min_v == max_v:
        return np.zeros(len(series), dtype=np.uint32)
    norm = (ranks - min_v) / (max_v - min_v)
    return (norm * (2**32 - 1)).astype(np.uint32)


def _spread_bits_2d(v: np.ndarray) -> np.ndarray:
    """Spread 32-bit integers into 64-bit space (every second bit)."""
    x = v.astype(np.uint64)
    x = (x | (x << np.uint64(16))) & np.uint64(0x0000FFFF0000FFFF)
    x = (x | (x << np.uint64(8)))  & np.uint64(0x00FF00FF00FF00FF)
    x = (x | (x << np.uint64(4)))  & np.uint64(0x0F0F0F0F0F0F0F0F)
    x = (x | (x << np.uint64(2)))  & np.uint64(0x3333333333333333)
    x = (x | (x << np.uint64(1)))  & np.uint64(0x5555555555555555)
    return x


def interleave_bits_2d(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Compute 2D Morton (Z-order) codes for two uint32 arrays."""
    return _spread_bits_2d(x) | (_spread_bits_2d(y) << np.uint64(1))


def interleave_bits_nd(arrays: Sequence[np.ndarray], bits_per_dim: int = 16) -> np.ndarray:
    """Interleave the top bits of N uint32 arrays into Morton order keys."""
    n_dims = len(arrays)
    n_rows = len(arrays[0])
    if n_rows == 0:
        return np.empty(0, dtype=np.uint64)

    if n_dims == 1:
        return arrays[0].astype(np.uint64)
    if n_dims == 2:
        return interleave_bits_2d(arrays[0], arrays[1])

    # For N >= 3: construct multi-dimensional Morton keys
    effective_bits = min(bits_per_dim, max(1, 64 // n_dims))
    morton_keys = np.zeros(n_rows, dtype=np.uint64)
    for bit_idx in range(effective_bits):
        src_shift = 31 - bit_idx
        for dim_idx in range(n_dims):
            dest_shift = (effective_bits - 1 - bit_idx) * n_dims + (n_dims - 1 - dim_idx)
            bit = ((arrays[dim_idx].astype(np.uint64) >> np.uint64(src_shift)) & np.uint64(1))
            morton_keys |= (bit << np.uint64(dest_shift))

    return morton_keys


def z_order_dataframe(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    """Sort DataFrame rows along a multi-dimensional Z-order (Morton) curve.

    Parameters:
        df: The pandas DataFrame to reorder.
        columns: The column names defining the multi-dimensional space.

    Returns:
        A new DataFrame reordered by Z-order curve with reset index.
    """
    if df.empty or not columns:
        return df.copy()

    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        return df.copy()

    if len(valid_cols) == 1:
        return df.sort_values(by=valid_cols[0]).reset_index(drop=True)

    uint_arrays = [normalize_to_uint32(df[c]) for c in valid_cols]
    z_keys = interleave_bits_nd(uint_arrays)
    sorted_indices = np.argsort(z_keys, kind="mergesort")
    return df.iloc[sorted_indices].reset_index(drop=True)

from __future__ import annotations
from typing import Optional, List, Union
import numpy as np

# ----------------------------
# Utilities
# ----------------------------


def _ensure_rng(rng: Optional[Union[int, np.random.Generator]]) -> np.random.Generator:
    if isinstance(rng, np.random.Generator):
        return rng
    return np.random.default_rng(rng)


def _ensure_float_if_needed(data: np.ndarray, strategy: str) -> np.ndarray:
    """Promotes integer arrays to float64 if the strategy requires NaNs or Infs."""
    floats_needed = ["insert_nan", "insert_inf", "insert_large_outliers"]
    if strategy in floats_needed and np.issubdtype(data.dtype, np.integer):
        return data.astype(np.float64)
    return data


def _get_domain_shape(domain: Optional[List[int]], col_idx: int) -> int:
    if domain is not None and 0 <= col_idx < len(domain):
        return domain[col_idx]
    return 0


# ----------------------------
# Strategy Implementations
# ----------------------------


def _gen_nan_row(d: int) -> np.ndarray:
    return np.full(d, np.nan)


def _gen_inf_row(d: int, rng: np.random.Generator) -> np.ndarray:
    row = np.zeros(d)
    choices = np.array([np.inf, -np.inf])
    for i in range(d):
        row[i] = rng.choice(choices)
    return row


def _gen_large_outlier_row(d: int, rng: np.random.Generator) -> np.ndarray:
    choices = np.array(
        [
            np.finfo(np.float64).max,
            np.finfo(np.float64).min,
            np.iinfo(np.int64).max,
            np.iinfo(np.int64).min,
        ],
        dtype=np.float64,
    )
    row = np.zeros(d)
    for i in range(d):
        row[i] = rng.choice(choices)
    return row


def _gen_shifted_outlier_row(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, d = data.shape
    if n == 0:
        return np.array([200.0] * d)

    row = np.zeros(d)
    shift = 200.0

    # Calculate min/max per column ignoring NaNs
    mins = np.nanmin(data, axis=0)
    maxs = np.nanmax(data, axis=0)

    for i in range(d):
        if rng.random() < 0.5:
            row[i] = mins[i] - shift
        else:
            row[i] = maxs[i] + shift
    return row


def _gen_domain_row(
    d: int, domain: Optional[List[int]], rng: np.random.Generator
) -> np.ndarray:
    row = np.zeros(d)
    for i in range(d):
        k = _get_domain_shape(domain, i)
        if k > 0:
            row[i] = rng.integers(0, k)
        else:
            row[i] = 0
    return row


def _gen_supported_row(
    data: np.ndarray, domain: Optional[List[int]], rng: np.random.Generator
) -> np.ndarray:
    n, d = data.shape
    if n == 0:
        return _gen_domain_row(d, domain, rng)

    row = np.zeros(d, dtype=data.dtype)
    for i in range(d):
        col_vals = data[:, i]
        # Valid observed values (ignoring NaN)
        uniques = np.unique(col_vals[~np.isnan(col_vals)])
        if len(uniques) > 0:
            row[i] = rng.choice(uniques)
        else:
            row[i] = 0
    return row


def _get_generated_row(
    data: np.ndarray,
    domain: Optional[List[int]],
    strategy: str,
    rng: np.random.Generator,
) -> np.ndarray:
    n, d = data.shape

    if strategy == "copy_random":
        if n > 0:
            idx = rng.integers(0, n)
            return data[idx].copy()
        return _gen_domain_row(d, domain, rng)

    elif strategy == "uniform_supported":
        return _gen_supported_row(data, domain, rng)

    elif strategy == "uniform_domain":
        return _gen_domain_row(d, domain, rng)

    elif strategy == "insert_nan":
        return _gen_nan_row(d)

    elif strategy == "insert_inf":
        return _gen_inf_row(d, rng)

    elif strategy == "insert_large_outliers":
        return _gen_large_outlier_row(d, rng)

    elif strategy == "insert_shifted_outliers":
        return _gen_shifted_outlier_row(data, rng)

    raise ValueError(f"Unknown strategy: {strategy}")


# ----------------------------
# Neighbor Functions
# ----------------------------


def neighbor_remove(
    data: np.ndarray,
    idx: Optional[int] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    **kwargs,
) -> np.ndarray:
    """Remove exactly one row from the array."""
    data = np.atleast_2d(data)
    n = data.shape[0]

    if n == 0:
        raise ValueError("Cannot remove from empty dataset.")

    rng = _ensure_rng(rng)
    target_idx = rng.integers(0, n) if idx is None else idx

    if not (0 <= target_idx < n):
        raise IndexError(f"Index {target_idx} out of bounds.")

    return np.delete(data, target_idx, axis=0)


def neighbor_add(
    data: np.ndarray,
    sample: Optional[Union[List, np.ndarray]] = None,
    domain: Optional[List[int]] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    strategy: str = "copy_random",
    **kwargs,
) -> np.ndarray:
    """Add exactly one row to the array."""
    data = np.atleast_2d(data)

    # If strategy requires float (like NaN), promote existing data first
    data = _ensure_float_if_needed(data, strategy)

    rng = _ensure_rng(rng)

    if sample is not None:
        new_row = np.array(sample)
    else:
        new_row = _get_generated_row(data, domain, strategy, rng)

    if new_row.ndim == 1:
        new_row = new_row.reshape(1, -1)

    return np.vstack([data, new_row])


def neighbor_replace(
    data: np.ndarray,
    idx: Optional[int] = None,
    sample: Optional[Union[List, np.ndarray]] = None,
    domain: Optional[List[int]] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    strategy: str = "modify_one_attr",
    **kwargs,
) -> np.ndarray:
    """Replace exactly one row in the array."""
    data = np.atleast_2d(data)
    n, d = data.shape

    if n == 0:
        raise ValueError("Cannot replace in empty dataset.")

    # If strategy requires float, promote types
    data = _ensure_float_if_needed(data, strategy)

    rng = _ensure_rng(rng)
    target_idx = rng.integers(0, n) if idx is None else idx

    # Copy to avoid mutating input
    new_data = data.copy()

    if sample is not None:
        new_data[target_idx] = np.array(sample)
        return new_data

    # Special logic for modify_one_attr
    if strategy == "modify_one_attr":
        row = new_data[target_idx].copy()
        col_idx = rng.integers(0, d)

        # Try to find 'supported' alternative values
        col_vals = data[:, col_idx]
        uniques = np.unique(col_vals[~np.isnan(col_vals)])
        current_val = row[col_idx]
        choices = uniques[uniques != current_val]

        if len(choices) > 0:
            row[col_idx] = rng.choice(choices)
        else:
            # Fallback to domain or brute force
            k = _get_domain_shape(domain, col_idx)
            if k > 1:
                new_val = rng.integers(0, k)
                while new_val == current_val:
                    new_val = rng.integers(0, k)
                row[col_idx] = new_val
            else:
                # If we can't modify just one attr, generate a whole new domain row
                row = _gen_domain_row(d, domain, rng)

        new_data[target_idx] = row
    else:
        # For all other strategies (nan, inf, shifted, etc.), generate full row
        new_row = _get_generated_row(data, domain, strategy, rng)
        new_data[target_idx] = new_row

    return new_data


def generate_neighbors(
    data: np.ndarray,
    k: int,
    mode: str = "unbounded",
    domain: Optional[List[int]] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    **kwargs,
) -> List[np.ndarray]:
    """
    Produce a list of k neighboring numpy arrays.
    """
    data = np.atleast_2d(data)
    rng = _ensure_rng(rng)

    for _ in range(k):
        if mode == "unbounded:add":
            ds = neighbor_add(data, domain=domain, rng=rng, **kwargs)
        elif mode == "unbounded:remove":
            ds = neighbor_remove(data, rng=rng, **kwargs)
        elif mode == "bounded:replace":
            ds = neighbor_replace(data, domain=domain, rng=rng, **kwargs)
        elif mode == "unbounded":
            if data.shape[0] == 0 or rng.random() < 0.5:
                ds = neighbor_add(data, domain=domain, rng=rng, **kwargs)
            else:
                ds = neighbor_remove(data, rng=rng, **kwargs)
        else:
            raise ValueError(f"Unknown mode '{mode}'")

    return ds

from __future__ import annotations
from typing import Optional, Union, Iterable, List, Dict, Any
import numpy as np
import pandas as pd
from typing import Protocol, runtime_checkable

# ----------------------------
# Utilities for RNG & coercion
# ----------------------------


def _ensure_rng(rng: Optional[Union[int, np.random.Generator]]) -> np.random.Generator:
    if isinstance(rng, np.random.Generator):
        return rng
    return np.random.default_rng(None if rng is None else rng)


def _template_dtypes(data: "DatasetLike") -> Optional[pd.Series]:
    """Best-effort peek at column dtypes from a tiny sample."""
    try:
        if data.records > 0:
            return data.to_dataframe(limit=1).dtypes
    except Exception:
        pass
    return None


class PandasDataset:
    """
    Lightweight, dependency-free dataset wrapper backed by a pandas DataFrame.

    Exposes the minimal API surface used by neighbor generation utilities:
      - domain.attrs, domain.shape
      - records
      - to_dataframe(columns, limit)
      - supported_values(attr)
      - size(attrs)
      - from_dataframe(classmethod)
    """

    class _Domain:
        def __init__(self, attrs: Iterable[str], shape: Iterable[int]):
            self.attrs = tuple(attrs)
            self.shape = tuple(int(x) for x in shape)
            self._map = dict(zip(self.attrs, self.shape))

        def size(self, attrs: Optional[Iterable[str]] = None) -> int:
            if attrs is None:
                prod = 1
                for v in self.shape:
                    prod *= int(v)
                return prod
            # Support both single attr and list of attrs
            if isinstance(attrs, (str, int)):
                return int(self._map[attrs])
            prod = 1
            for a in attrs:
                prod *= int(self._map[a])
            return prod

    def __init__(
        self,
        df: pd.DataFrame,
        domain_attrs: Iterable[str],
        domain_shape: Iterable[int],
        *,
        log_queries: bool = False,
        discretize: bool = False,
    ):
        domain_attrs = list(domain_attrs)
        self._df = df.loc[:, domain_attrs].copy()
        self.domain = PandasDataset._Domain(domain_attrs, domain_shape)
        self.log_queries = log_queries
        self.discretize = discretize

    @property
    def records(self) -> int:
        return int(len(self._df))

    def to_dataframe(
        self,
        columns: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        **_kwargs,
    ) -> pd.DataFrame:
        cols = list(columns) if columns is not None else list(self.domain.attrs)
        out = self._df.loc[:, cols]
        if limit is not None:
            out = out.head(int(limit))
        return out.copy()

    def supported_values(self, attr: str) -> List[Any]:
        if attr not in self._df.columns:
            return []
        vals = self._df[attr].dropna().unique().tolist()
        return vals

    def size(self, attrs: Optional[Iterable[str]] = None) -> int:
        return self.domain.size(attrs)

    @staticmethod
    def create_domain_from_dataframe(df: pd.DataFrame) -> Dict[str, int]:
        return {c: int(df[c].nunique()) for c in df.columns}

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        domain_dict: Optional[Dict[str, int]] = None,
        log_queries: bool = False,
        discretize: bool = False,
    ) -> "PandasDataset":
        if domain_dict is None:
            domain_dict = cls.create_domain_from_dataframe(df)
        attrs = list(domain_dict.keys())
        shape = [int(domain_dict[a]) for a in attrs]
        return cls(df, attrs, shape, log_queries=log_queries, discretize=discretize)


def _new_dataset_like(original: "DatasetLike", df: pd.DataFrame) -> "DatasetLike":
    """
    Build a new Dataset from a pandas DataFrame while preserving the
    original domain (attrs + sizes), log_queries, and discretization flag.
    """
    domain_dict = dict(zip(original.domain.attrs, original.domain.shape))
    # Ensure column order matches domain
    df = df[list(original.domain.attrs)]
    return type(original).from_dataframe(
        df,
        domain_dict=domain_dict,
        log_queries=original.log_queries,
        discretize=original.discretize,
    )


def _align_sample_to_columns(
    sample: Union[Dict[str, Any], pd.Series, Iterable[Any], np.ndarray],
    cols: Iterable[str],
    data: "DatasetLike",
) -> pd.DataFrame:
    """
    Convert a user-provided sample into a 1-row DataFrame aligned with dataset columns.
    Attempts to coerce to observed dtypes (if any rows exist). Otherwise leaves values as-is.
    """
    cols = list(cols)
    if isinstance(sample, pd.Series):
        sample = sample.to_dict()

    if isinstance(sample, dict):
        extra = set(sample.keys()) - set(cols)
        if extra:
            raise ValueError(f"Sample has unknown columns: {sorted(extra)}")
        row = {c: sample.get(c) for c in cols}
    else:
        vals = list(sample)
        if len(vals) != len(cols):
            raise ValueError(
                f"Positional sample must have {len(cols)} values, got {len(vals)}"
            )
        row = dict(zip(cols, vals))

    dtypes = _template_dtypes(data)
    if dtypes is None:
        # No dtype info available; return as-is
        return pd.DataFrame([row], columns=cols)

    coerced = {}
    for c in cols:
        v = row[c]
        dtype = dtypes.get(c)
        try:
            if dtype is not None and pd.api.types.is_integer_dtype(dtype):
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    raise TypeError(f"Column {c} cannot be NaN for integer dtype")
                coerced[c] = int(v)
            elif dtype is not None and hasattr(dtype, "type"):
                coerced[c] = dtype.type(v)
            else:
                coerced[c] = v
        except Exception:
            coerced[c] = v
    return pd.DataFrame([coerced], columns=cols)


# ----------------------------
# Domain & sampling helpers
# ----------------------------


def _domain_cardinality(data: "DatasetLike", attr: str) -> int:
    return int(data.size([attr]))


def _random_row_from_supported(
    data: "DatasetLike", rng: np.random.Generator
) -> pd.DataFrame:
    row = {}
    for attr in data.domain.attrs:
        support_vals = data.supported_values(attr)
        if len(support_vals) == 0:
            # Fallback: sample from [0, k-1] if we have a declared domain size
            k = _domain_cardinality(data, attr)
            row[attr] = int(rng.integers(0, k)) if k > 0 else 0
        else:
            # Choose uniformly from actually observed values (type-safe)
            row[attr] = rng.choice(support_vals)
    return pd.DataFrame([row], columns=list(data.domain.attrs))


def _random_row_from_domain(
    data: "DatasetLike", rng: np.random.Generator
) -> pd.DataFrame:
    """
    Uniform over [0..k-1] per attribute. Only appropriate for integer-coded domains.
    """
    row = {
        attr: int(rng.integers(0, _domain_cardinality(data, attr)))
        for attr in data.domain.attrs
    }
    return pd.DataFrame([row], columns=list(data.domain.attrs))


def _random_nan_row(data: "DatasetLike", rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate a row where each attribute is NaN.
    """
    row = {}
    for attr in data.domain.attrs:
        row[attr] = np.nan
    return pd.DataFrame([row], columns=list(data.domain.attrs))


def _random_inf_row(data: "DatasetLike", rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate a row where each attribute is randomly chosen from [Inf, -Inf].
    """
    row = {}
    choices = [np.inf, -np.inf]
    for attr in data.domain.attrs:
        row[attr] = rng.choice(choices)
    return pd.DataFrame([row], columns=list(data.domain.attrs))


def _random_large_outlier_row(
    data: "DatasetLike", rng: np.random.Generator
) -> pd.DataFrame:
    """
    Generate a row where each attribute is randomly chosen from very large values.
    """
    row = {}
    # Mix of large integer/float boundaries. We pick by index to avoid
    # numpy array type promotion that might lose precision on specific types.
    choices = [
        np.iinfo(np.int64).max,
        np.iinfo(np.int64).min,
        np.finfo(np.float64).max,
        np.finfo(np.float64).min,
    ]
    for attr in data.domain.attrs:
        idx = rng.integers(0, len(choices))
        row[attr] = choices[idx]
    return pd.DataFrame([row], columns=list(data.domain.attrs))


def _random_shifted_outlier_row(
    data: "DatasetLike", rng: np.random.Generator
) -> pd.DataFrame:
    """
    Generate a row where each attribute is a shifted version of the dataset's min/max.
    """
    row = {}
    df = data.to_dataframe()
    shift = 200

    for attr in data.domain.attrs:
        # Default if empty or non-numeric
        val = shift if rng.random() < 0.5 else -shift

        if data.records > 0 and attr in df.columns:
            col_data = df[attr]
            # Check if numeric
            if pd.api.types.is_numeric_dtype(col_data):
                min_val = col_data.min()
                max_val = col_data.max()

                if rng.random() < 0.5:
                    val = min_val - shift
                else:
                    val = max_val + shift

                if pd.api.types.is_integer_dtype(col_data):
                    val = int(val)

        row[attr] = val
    return pd.DataFrame([row], columns=list(data.domain.attrs))



def _copy_random_row_df(data: "DatasetLike", rng: np.random.Generator) -> pd.DataFrame:
    if data.records == 0:
        return pd.DataFrame(columns=list(data.domain.attrs))
    df = data.to_dataframe(columns=data.domain.attrs)
    # Use a deterministic seed derived from rng
    seed = int(rng.integers(0, 2**32 - 1))
    return df.sample(n=1, random_state=seed).reset_index(drop=True)


# -------- Unbounded adjacency (add/remove one record) --------


def neighbor_remove(
    data: "DatasetLike",
    idx: Optional[int] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
) -> "DatasetLike":
    """
    Return a neighbor by removing exactly one record (unbounded adjacency).
    If idx is None, remove a uniformly random row.
    """
    n = int(data.records)
    if n == 0:
        raise ValueError("Cannot remove from an empty dataset.")
    rng = _ensure_rng(rng)
    drop_idx = int(rng.integers(0, n)) if idx is None else int(idx)
    if not (0 <= drop_idx < n):
        raise IndexError(
            f"idx {drop_idx} is out of range for dataset with {n} records."
        )

    df = data.to_dataframe(columns=data.domain.attrs)
    new_df = df.drop(df.index[drop_idx]).reset_index(drop=True)
    return _new_dataset_like(data, new_df)


def neighbor_add(
    data: "DatasetLike",
    sample: Optional[
        Union[Dict[str, Any], pd.Series, Iterable[Any], np.ndarray]
    ] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    strategy: str = "copy_random",
) -> "DatasetLike":
    """
    Return a neighbor by adding exactly one record (unbounded adjacency).

    strategy:
      - "copy_random": duplicate a uniformly random existing row (fallback to uniform_domain if empty)
      - "uniform_supported": sample each attribute from observed supports
      - "uniform_domain": sample each attribute uniformly from [0..k-1] (int-coded only)
      - "insert_nan": sample each attribute as NaN
      - "insert_inf": sample each attribute randomly from [Inf, -Inf]
      - "insert_large_outliers": sample each attribute randomly from very large values
      - "insert_shifted_outliers": sample each attribute from min/max +/- 200

    If 'sample' is provided, it takes precedence and must align with the dataset schema.
    """
    rng = _ensure_rng(rng)
    cols = list(data.domain.attrs)

    if sample is not None:
        row_df = _align_sample_to_columns(sample, cols, data)
    else:
        if strategy == "copy_random":
            if data.records == 0:
                row_df = _random_row_from_domain(data, rng)
            else:
                row_df = _copy_random_row_df(data, rng)
        elif strategy == "uniform_supported":
            row_df = _random_row_from_supported(data, rng)
        elif strategy == "uniform_domain":
            row_df = _random_row_from_domain(data, rng)
        elif strategy == "insert_nan":
            row_df = _random_nan_row(data, rng)
        elif strategy == "insert_inf":
            row_df = _random_inf_row(data, rng)
        elif strategy == "insert_large_outliers":
            row_df = _random_large_outlier_row(data, rng)
        elif strategy == "insert_shifted_outliers":
            row_df = _random_shifted_outlier_row(data, rng)
        else:
            raise ValueError(f"Unknown strategy '{strategy}'.")

    base_df = data.to_dataframe(columns=cols)
    new_df = pd.concat([base_df, row_df], ignore_index=True)
    return _new_dataset_like(data, new_df)


# -------- Bounded adjacency (replace exactly one record) --------


def neighbor_replace(
    data: "DatasetLike",
    idx: Optional[int] = None,
    sample: Optional[
        Union[Dict[str, Any], pd.Series, Iterable[Any], np.ndarray]
    ] = None,
    rng: Optional[Union[int, np.random.Generator]] = None,
    strategy: str = "modify_one_attr",
) -> "DatasetLike":
    """
    Return a neighbor with the same number of records that differs in exactly one row (bounded adjacency).

    - If `sample` is given, row at `idx` (random if None) is replaced by it (schema-validated).
    - If `strategy == "modify_one_attr"`, mutate a single random attribute of a random row,
      drawing a different value from observed supports if possible (type-safe).
    - If `strategy == "uniform_supported"`, the replacement row is sampled from observed supports.
    - If `strategy == "uniform_domain"`, the replacement row is sampled uniformly from [0..k-1] (int-coded only).
    - If `strategy == "insert_nan"`, the replacement row is sampled as NaN.
    - If `strategy == "insert_inf"`, the replacement row is sampled from [Inf, -Inf].
    - If `strategy == "insert_large_outliers"`, the replacement row is sampled from very large values.
    - If `strategy == "insert_shifted_outliers"`, the replacement row is sampled from min/max +/- 200.
    """
    n = int(data.records)
    if n == 0:
        raise ValueError("Cannot replace a row in an empty dataset.")
    rng = _ensure_rng(rng)
    cols = list(data.domain.attrs)
    target_idx = int(rng.integers(0, n)) if idx is None else int(idx)
    if not (0 <= target_idx < n):
        raise IndexError(
            f"idx {target_idx} is out of range for dataset with {n} records."
        )

    df = data.to_dataframe(columns=cols)
    current_row = df.iloc[target_idx : target_idx + 1].reset_index(drop=True)

    if sample is not None:
        row_df = _align_sample_to_columns(sample, cols, data)
    elif strategy == "modify_one_attr":
        # Copy the row and tweak exactly one attribute to a different value
        row = current_row.iloc[0].to_dict()
        attr = cols[int(rng.integers(0, len(cols)))]
        support = data.supported_values(attr)

        if len(support) > 1:
            # Choose a different value from observed supports (type-safe)
            cur = row[attr]
            choices = [v for v in support if v != cur]
            row[attr] = rng.choice(choices)
            row_df = pd.DataFrame([row], columns=cols)
        else:
            # Fall back to domain-based change if support is degenerate
            k = _domain_cardinality(data, attr)
            if k <= 1:
                # Replace whole row from domain if even the domain is degenerate
                row_df = _random_row_from_domain(data, rng)
            else:
                cur = row[attr]
                alt = (
                    [v for v in range(k) if v != cur]
                    if isinstance(cur, (int, np.integer))
                    else list(range(k))
                )
                row[attr] = int(rng.choice(alt))
                row_df = pd.DataFrame([row], columns=cols)
    elif strategy == "uniform_supported":
        row_df = _random_row_from_supported(data, rng)
    elif strategy == "uniform_domain":
        row_df = _random_row_from_domain(data, rng)
    elif strategy == "insert_nan":
        row_df = _random_nan_row(data, rng)
    elif strategy == "insert_inf":
        row_df = _random_inf_row(data, rng)
    elif strategy == "insert_large_outliers":
        row_df = _random_large_outlier_row(data, rng)
    elif strategy == "insert_shifted_outliers":
        row_df = _random_shifted_outlier_row(data, rng)
    else:
        raise ValueError(f"Unknown strategy '{strategy}'.")

    # Replace the row
    new_df = df.copy()
    for c in cols:
        new_df.at[target_idx, c] = row_df.iloc[0][c]
    return _new_dataset_like(data, new_df)


import numpy as np


def uniform_sample(ds, seed=None, low: float = -1.0, high: float = 1.0):
    """
    Draw a uniform numeric value for each attribute in ds.domain.attrs.
    """
    rng = np.random.default_rng(seed)
    return {a: float(rng.uniform(low, high)) for a in ds.domain.attrs}


def gaussian_sample(ds, seed=None, mean: float = 0.0, sigma: float = 1_000.0):
    """
    Draw a Gaussian numeric value (large variance by default) per attribute.
    """
    rng = np.random.default_rng(seed)
    return {a: float(rng.normal(mean, sigma)) for a in ds.domain.attrs}


def random_index(ds: "DatasetLike", seed=None) -> int:
    """
    Pick a random valid row index from the dataset.
    """
    n = int(ds.records)
    if n <= 0:
        raise ValueError("Cannot select a random index from an empty dataset.")
    rng = np.random.default_rng(seed)
    return int(rng.integers(0, n))


def generate_neighbors(
    data: "DatasetLike",
    k: int,
    mode: str = "unbounded",
    rng: Optional[Union[int, np.random.Generator]] = None,
    **kwargs,
) -> List["DatasetLike"]:
    """
    Produce a list of k neighboring datasets.

    mode:
      - "unbounded:add"    -> apply neighbor_add
      - "unbounded:remove" -> apply neighbor_remove
      - "bounded:replace"  -> apply neighbor_replace
      - "unbounded"        -> pick add/remove at random each time

    kwargs are forwarded to the underlying neighbor_* function(s).
    """
    if k <= 0:
        return []
    rng = _ensure_rng(rng)
    out: List["DatasetLike"] = []
    for _ in range(k):
        if mode == "unbounded:add":
            out.append(neighbor_add(data, rng=rng, **kwargs))
        elif mode == "unbounded:remove":
            out.append(neighbor_remove(data, rng=rng, **kwargs))
        elif mode == "bounded:replace":
            out.append(neighbor_replace(data, rng=rng, **kwargs))
        elif mode == "unbounded":
            if int(data.records) == 0:
                out.append(neighbor_add(data, rng=rng, **kwargs))
            else:
                if rng.random() < 0.5:
                    out.append(neighbor_remove(data, rng=rng, **kwargs))
                else:
                    out.append(neighbor_add(data, rng=rng, **kwargs))
        else:
            raise ValueError(f"Unknown mode '{mode}'.")
    return out


@runtime_checkable
class DatasetLike(Protocol):
    domain: Any
    log_queries: bool
    discretize: bool

    @property
    def records(self) -> int: ...

    def to_dataframe(
        self,
        columns: Optional[Iterable[str]] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> pd.DataFrame: ...

    def supported_values(self, attr: str) -> List[Any]: ...

    def size(self, attrs: Optional[Iterable[str]] = None) -> int: ...

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        domain_dict: Optional[Dict[str, int]] = None,
        log_queries: bool = False,
        discretize: bool = False,
    ) -> "DatasetLike": ...

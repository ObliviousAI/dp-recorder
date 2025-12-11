import numpy as np
from dp_accounting.pld import privacy_loss_distribution as pld


def pld_from_epsilon_delta_curve(
    epsilons,
    deltas,
    value_discretization_interval: float = 1e-4,
    add_anchors: bool = True,
    min_delta_floor: float | None = None,  # e.g. 1e-300 to avoid 0 underflow
):
    eps = np.asarray(epsilons, dtype=float)
    dlt = np.asarray(deltas, dtype=float)
    if eps.shape != dlt.shape:
        raise ValueError("epsilons and deltas must have the same shape")

    # sort by epsilon
    order = np.argsort(eps)
    eps, dlt = eps[order], dlt[order]

    # enforce δ non-increasing in ε (prefix min, not suffix min!)
    dlt = np.minimum.accumulate(dlt)

    # clip to [0, 1]; optionally lift exact zeros to a tiny floor to prevent collapse
    dlt = np.clip(dlt, 0.0, 1.0)
    if min_delta_floor is not None:
        dlt = np.maximum(dlt, float(min_delta_floor))

    dx = float(value_discretization_interval)
    if not (dx > 0 and np.isfinite(dx)):
        raise ValueError(
            "value_discretization_interval must be a positive finite float"
        )

    # optional anchors (only if you don't already have endpoints)
    if add_anchors:
        if eps[0] > 0.0:
            eps = np.insert(eps, 0, 0.0)
            dlt = np.insert(dlt, 0, 1.0)

        eps = np.append(eps, eps[-1] + dx)
        dlt = np.append(dlt, max(0.0, dlt[-1] - 0.0))  # typically 0.0 is fine

    # discretize (pessimistic): round ε up to the nearest grid point
    k_idx = np.ceil(eps / dx).astype(int)

    # collapse duplicates on each grid index using the MIN δ (strongest bound)
    per_k_min_delta = {}
    for k, delta in zip(k_idx, dlt):
        per_k_min_delta[k] = min(per_k_min_delta.get(k, 1.0), float(delta))

    ks = np.array(sorted(per_k_min_delta.keys()), dtype=int)
    deltas_clean = np.array([per_k_min_delta[k] for k in ks], dtype=float)

    pmf = pld.pld_pmf.create_pmf_pessimistic_connect_dots(dx, ks, deltas_clean)
    return pld.PrivacyLossDistribution(pmf), ks, deltas_clean

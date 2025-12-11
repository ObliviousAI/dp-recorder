from typing import Optional, Union
import numpy as np

from agent_audit.auditing.audit_primitives import audit_spec
from dp_accounting.pld import privacy_loss_distribution


def dist_linf(a: np.ndarray, b: np.ndarray) -> float:
    return np.linalg.norm(a - b, ord=np.inf)


def dist_l1(a: np.ndarray, b: np.ndarray) -> float:
    return np.linalg.norm(a - b, ord=1)


@audit_spec(
    kind="Laplace",
    input_arg="values",
    sensitivity_arg="l1_sensitivity",
    metric_fn=dist_l1,
)
def apply_laplace_noise(
    values: np.ndarray,
    *,
    l1_sensitivity: float,
    noise_multiplier: float,
) -> Union[float, np.ndarray]:
    scale = l1_sensitivity * noise_multiplier
    return values + np.random.laplace(loc=0, scale=scale, size=values.shape)


def exponential_pld(
    l_infinity_sensitivity: float,
    noise_multiplier: float,
    monotonic: bool = False,
    log_base: Optional[float] = None,
    value_discretization_interval: float = 1e-4,
) -> privacy_loss_distribution.PrivacyLossDistribution:
    """
    Vadym Doroshenko's implementation of the tight dominating bounded range PLD for the exponential mechanism.
    https://github.com/dvadym/dp/blob/main/dp_accounting/exponential_pld.py
    """

    br_eps = 1 / (l_infinity_sensitivity * noise_multiplier)

    def calc_delta(x: np.ndarray) -> np.ndarray:
        return (np.exp(br_eps / 2) - np.exp(x / 2)) ** 2 / (np.exp(br_eps) - 1)

    N = int(np.ceil(br_eps / value_discretization_interval))
    rounded_epsilons = np.linspace(-N, N, num=2 * N + 1)
    epsilons = rounded_epsilons * value_discretization_interval
    deltas = np.zeros_like(epsilons, dtype=float)
    deltas[1:-1] = calc_delta(epsilons[1:-1])
    deltas[0] = -np.expm1(-N * value_discretization_interval)

    return privacy_loss_distribution.PrivacyLossDistribution(
        privacy_loss_distribution.pld_pmf.create_pmf_pessimistic_connect_dots(
            value_discretization_interval, rounded_epsilons, deltas
        )
    )


@audit_spec(
    kind="Gumbel Top-1",
    input_arg="q",
    sensitivity_arg="l_infinity_sensitivity",
    metric_fn=dist_linf,
    accountant=exponential_pld,
)
def top_one(
    q: np.ndarray,
    *,
    l_infinity_sensitivity: float,
    noise_multiplier: float,
):
    """
    Selects an index using the Exponential Mechanism, implemented via
    OpenDP's make_report_noisy_max_gumbel.

    Returns:
        The selected index (int).
    """
    scale = l_infinity_sensitivity * noise_multiplier
    noisy_scores = q + np.random.gumbel(loc=0.0, scale=scale, size=q.shape)
    return int(np.argmax(noisy_scores))

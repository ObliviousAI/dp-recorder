import numpy as np
from dp_recorder.auditing.audit_primitives import audit_spec


# --- 1. Setup Distance Metric and Mock Mechanism ---
def dist_l1(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b, ord=1))


@audit_spec(
    kind="Laplace",
    input_arg="values",
    sensitivity_arg="l1_sensitivity",
    metric_fn=dist_l1,
)
def instrumented_laplace(values, l1_sensitivity, epsilon):
    """Mocking a trusted Laplace mechanism."""
    scale = l1_sensitivity / epsilon
    return values + np.random.laplace(loc=0.0, scale=scale, size=values.shape)


def test_laplace_mechanism():
    values = np.array([1.0, 2.0, 3.0])
    l1_sensitivity = 1.0
    epsilon = 1.0
    noisy_values = instrumented_laplace(values, l1_sensitivity, epsilon)
    assert noisy_values.shape == values.shape
    assert noisy_values.dtype == values.dtype

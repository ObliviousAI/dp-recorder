import numpy as np
import pytest
from dp_recorder.auditing.audit_primitives import Auditor
from laplace_mechanism import instrumented_laplace


# --- 3. Pathological Inputs (NaN Injection) ---
def buggy_nan_clipping(data, epsilon):
    # BUG: Naive clipping fails on NaN (Section 4.3.9).
    limit = 5.0
    # Naive clip: np.clip ignores NaNs. They remain in the array.
    clipped_data = np.clip(data, -limit, limit)

    raw_sum = np.sum(clipped_data)  # Becomes NaN
    noisy_sum = instrumented_laplace(
        np.array([raw_sum]), l1_sensitivity=limit, epsilon=epsilon
    )
    return noisy_sum[0]


def test_nan_injection_bug():
    data = np.array([1.0, 2.0])
    neighbor = np.array([1.0, np.nan])  # Adversarial neighbor

    auditor = Auditor()
    with auditor:
        buggy_nan_clipping(data, epsilon=1.0)

    auditor.set_replay()
    with auditor:
        buggy_nan_clipping(neighbor, epsilon=1.0)

    # DETERMINISTIC CHECK:
    # Distance calculation results in NaN. The auditor's validation
    # (distance <= sensitivity) fails to evaluate to True (NaN <= 5.0 is False),
    # throwing an error.
    with pytest.raises(AssertionError):
        auditor.validate_records()

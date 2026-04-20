"""
Minimal example of noise miscalibration.

Maps to: the Synthcity PrivBayes issue discussed in
https://arxiv.org/abs/2602.17454
Why this example: the declared sensitivity, and therefore the noise scale,
collapses to zero when K == n_features.
Note: this is a reduced analogue, not a line-by-line reproduction of the
library code.
"""

import numpy as np
import pytest
from dp_recorder.auditing.audit_primitives import Auditor
from laplace_mechanism import instrumented_laplace


# --- 1. Noise Miscalibration ---
def buggy_privbayes_noise(data, n_features, K, epsilon):
    # BUG: Emulates the Synthcity PrivBayes bug (Section 4.3.3).
    # If K equals n_features, the sensitivity/scale evaluates to zero,
    # disabling privacy!
    calculated_sensitivity = float(n_features - K)

    raw_sum = np.sum(data)
    noisy_sum = instrumented_laplace(
        np.array([raw_sum]), l1_sensitivity=calculated_sensitivity, epsilon=epsilon
    )
    return noisy_sum[0]


def test_noise_miscalibration_bug():
    data = np.array([1.0, 1.0])
    neighbor = np.array([1.0])  # Add/Remove adjacency
    auditor = Auditor()

    # Trigger the bug where K == n_features
    n_features = 5
    K = 5

    with auditor:
        buggy_privbayes_noise(data, n_features, K, epsilon=1.0)

    auditor.set_replay()
    with auditor:
        buggy_privbayes_noise(neighbor, n_features, K, epsilon=1.0)

    # DETERMINISTIC CHECK:
    # The empirical distance between sum(data)=2.0 and sum(neighbor)=1.0 is 1.0.
    # The declared sensitivity passed to the mechanism is 0.0.
    # Since 1.0 > 0.0, the auditor immediately catches the miscalibration.
    with pytest.raises(AssertionError) as exc_info:
        auditor.validate_records()

    message = str(exc_info.value)
    assert "Sens" in message
    print(f"Caught expected AssertionError:\n{message}", flush=True)

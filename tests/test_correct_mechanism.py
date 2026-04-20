"""
Minimal example of a correct differentially private counting mechanism.

Purpose: provides a passing reference example for the auditor.
Why this example: counting ones in binary data has global L1 sensitivity 1 under
add/remove adjacency.
Note: this file is a sanity check, not a reproduction of a real-world bug.
"""

import numpy as np
from dp_recorder.auditing.audit_primitives import Auditor
from laplace_mechanism import instrumented_laplace


# --- 1. A Correct DP Count Mechanism ---
def dp_count_mechanism(data, epsilon):
    # For binary data, adding or removing one record changes the count of 1s by at
    # most 1, so the global L1 sensitivity is 1.
    raw_count = np.sum(np.asarray(data) == 1)
    noisy_count = instrumented_laplace(
        np.array([raw_count], dtype=float), l1_sensitivity=1.0, epsilon=epsilon
    )
    return noisy_count[0]


# --- 2. The Audit Test ---
def test_correct_count_mechanism():
    # Dataset D contains two ones.
    data = np.array([0, 1, 1, 0])

    # Neighbor D' differs by removing a single 1, so the true count changes by 1.
    neighbor = np.array([0, 1, 0])

    auditor = Auditor()

    with auditor:
        dp_count_mechanism(data, epsilon=1.0)

    auditor.set_replay()
    with auditor:
        dp_count_mechanism(neighbor, epsilon=1.0)

    # The observed distance is 1 and matches the declared sensitivity, so the
    # deterministic audit should pass without raising.
    auditor.validate_records()

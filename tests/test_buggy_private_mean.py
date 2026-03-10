import numpy as np
from dp_recorder.auditing.audit_primitives import Auditor, ensure_equality
from laplace_mechanism import instrumented_laplace
import pytest


# --- 1. The Buggy Implementation ---
def buggy_private_mean(data, epsilon):
    # BUG: len(data) is private under add/remove adjacency!
    n = len(data)

    # We instruct the framework that 'n' acts as a public scaling factor
    # and MUST remain data-independent.

    clip_limit = 1.0
    clipped_data = np.clip(data, -clip_limit, clip_limit)
    raw_sum = np.sum(clipped_data)

    noisy_sum = instrumented_laplace(
        np.array([raw_sum]), l1_sensitivity=clip_limit, epsilon=epsilon
    )

    # The divisor 'n' changes depending on the existence of a single user
    ensure_equality(n=n)

    return noisy_sum[0] / n


# --- 2. The Audit Test ---
def test_invariant_violation():
    # Dataset D: Dataset has 3 records
    data = np.array([0.5, 0.5, 0.5])

    # Dataset D': Add/Remove adjacency means neighbor has 2 records
    neighbor = np.array([0.5, 0.5])

    auditor = Auditor()

    with auditor:
        buggy_private_mean(data, epsilon=1.0)

    auditor.set_replay()

    # DETERMINISTIC CHECK:
    # The `ensure_equality` hook intercepts the `n` variable.
    # Because 3 != 2, it immediately flags an Invariance Violation,
    # pinpointing the exact line where the dataset size leaked.
    with pytest.raises(AssertionError):
        with auditor:
            buggy_private_mean(neighbor, epsilon=1.0)

        auditor.validate_records()

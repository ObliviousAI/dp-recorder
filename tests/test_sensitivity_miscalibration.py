import numpy as np
from dp_recorder.auditing.audit_primitives import Auditor, audit_spec
from laplace_mechanism import instrumented_laplace
import pytest


# --- 2. The Buggy Implementation ---
def buggy_private_sum(data, epsilon):
    clip_limit = 5.0

    # Intended sanitization to enforce a strict sensitivity bound
    clipped_data = np.clip(data, -clip_limit, clip_limit)

    # Sensitivity is calculated assuming 'clipped_data' will be used
    declared_sensitivity = clip_limit

    # BUG: The developer accidentally computes the sum on 'data' (raw)
    # instead of 'clipped_data' (censored).
    raw_sum = np.sum(data)

    results = instrumented_laplace(
        np.array([raw_sum]), l1_sensitivity=declared_sensitivity, epsilon=epsilon
    )
    return results[0]


# --- 3. The Audit Test ---
def test_sensitivity_bug():
    # Dataset D: A dataset strictly within the expected clipping bounds
    data = np.array([1.0, -2.0, 3.0])

    # Dataset D': A neighboring dataset with a massive, malicious outlier
    neighbor = np.array([1.0, -2.0, 100.0])

    auditor = Auditor()

    # Phase 1: Record on D
    with auditor:
        buggy_private_sum(data, epsilon=1.0)

    # Phase 2: Replay on D'
    auditor.set_replay()
    with auditor:
        buggy_private_sum(neighbor, epsilon=1.0)

    # DETERMINISTIC CHECK:
    # Measures ||sum(D) - sum(D')||_1 -> |2.0 - 99.0| = 97.0
    # Compares 97.0 against the declared_sensitivity of 5.0.
    # Because 97.0 > 5.0, this will raise a Sensitivity Miscalibration exception!

    with pytest.raises(AssertionError):
        auditor.validate_records()
        auditor.run_distributional_audit(n_samples=10000, alpha=0.95)

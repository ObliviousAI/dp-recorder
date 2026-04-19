"""
Minimal example of privacy-budget double spending.

Maps to: a canonical privacy-accounting bug pattern used in the artifact.
Why this example: two queries each spend the full epsilon even though the
pipeline intends epsilon total.
Note: this is a reduced analogue rather than a reproduction of a specific
library bug from the paper.
"""

import numpy as np
from dp_recorder.auditing.audit_primitives import Auditor
from laplace_mechanism import instrumented_laplace
import pytest

# --- 1. The Buggy Implementation ---
def buggy_multiple_queries(data, epsilon):
    # BUG: Developer applies two mechanisms to the data, spending full
    # `epsilon` on each, but the overall pipeline intends to only spend
    # `epsilon` total. (Should be epsilon/2)

    # Query 1
    raw_sum = np.sum(data)
    noisy_sum = instrumented_laplace(
        np.array([raw_sum]), l1_sensitivity=1.0, epsilon=epsilon
    )

    # Query 2 (Double dipping into the privacy budget)
    raw_count = len(data)
    noisy_count = instrumented_laplace(
        np.array([raw_count]), l1_sensitivity=1.0, epsilon=epsilon
    )

    return noisy_sum[0], noisy_count[0]


def test_accounting_bug():
    # Dataset D and D' differing by 1 row
    data = np.zeros(100)
    neighbor = np.append(data, 1.0)

    eps_target = 1.0

    auditor = Auditor()

    with auditor:
        buggy_multiple_queries(data, epsilon=eps_target)

    auditor.set_replay()
    with auditor:
        buggy_multiple_queries(neighbor, epsilon=eps_target)

    # Structural checks will pass (sensitivities are individually respected)
    auditor.validate_records()

    # STATISTICAL CHECK (Re:cord-play-sample):
    # Generates thousands of samples of the isolated trace to compute the real PLD
    auditor.run_distributional_audit(n_samples=10000, alpha=0.95)
    auditor.compute_overall_pld()

    # Extract the empirical privacy guarantee
    got_epsilon = auditor.get_overall_current_guarantee(delta=1e-5)

    print(f"Target Epsilon: {eps_target} | Empirical Epsilon: {got_epsilon:.2f}")

    # The auditor will calculate that the empirical loss is nearly 2.0.
    # This assertion will FAIL, alerting the developer to the bad accounting!
    with pytest.raises(AssertionError) as exc_info:
        assert got_epsilon <= eps_target, "Privacy budget exceeded!"

    message = str(exc_info.value)
    assert "Privacy budget exceeded!" in message
    print(f"Caught expected AssertionError:\n{message}", flush=True)

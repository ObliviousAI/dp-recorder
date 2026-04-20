"""
Minimal example of domain inference from private data.

Maps to: the Diffprivlib and dpmm issues discussed in
https://arxiv.org/abs/2602.17454
Why this example: the inferred set of classes depends on private data and
changes control flow.
Note: this is a reduced analogue, not a line-by-line reproduction of the
library code.
"""

import numpy as np
import pytest
from dp_recorder.auditing.audit_primitives import Auditor, ensure_equality
from laplace_mechanism import instrumented_laplace


# --- 2. Invariant Violation via Domain Inference (Diffprivlib / dpmm Bug) ---
def buggy_domain_inference(data, epsilon):
    # BUG: Emulates Diffprivlib and dpmm inferring classes directly from private data.
    # Under Add/Remove adjacency, a dataset might entirely lose a rare class!
    classes = np.unique(data)

    # The framework requires us to assert that metadata like num_classes is invariant
    ensure_equality(num_classes=len(classes))

    results = []
    # Data-dependent control flow loop
    for c in classes:
        count = np.sum(data == c)
        res = instrumented_laplace(
            np.array([count]), l1_sensitivity=1.0, epsilon=epsilon / len(classes)
        )
        results.append(res[0])
    return results


def test_domain_inference_bug():
    # Dataset D: Contains 3 distinct classes
    data = np.array([0, 1, 2, 0])

    # Dataset D': Remove adjacency -> rare class '2' is completely removed
    neighbor = np.array([0, 1, 0])
    auditor = Auditor()

    # Phase 1: Record on D
    with auditor:
        buggy_domain_inference(data, epsilon=1.0)

    auditor.set_replay()

    # Phase 2: Replay on D'
    # DETERMINISTIC CHECK:
    # During Replay on D', the length of 'classes' diverges from 3 to 2.
    # The ensure_equality hook catches this data-dependent control flow
    # leakage immediately.
    with pytest.raises(AssertionError) as exc_info:
        with auditor:
            buggy_domain_inference(neighbor, epsilon=1.0)

    message = str(exc_info.value)
    assert "Equality Failure" in message
    assert "num_classes" in message
    print(f"Caught expected AssertionError:\n{message}", flush=True)

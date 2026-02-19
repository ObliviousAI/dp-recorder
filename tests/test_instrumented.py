import example_library_instrumented.audited_algorithm as audited_algorithm
from dp_recorder.auditing.audit_primitives import Auditor
import pandas as pd
import numpy as np
from dp_recorder.auditing.dataset_util import generate_neighbors

import pytest
import os


@pytest.mark.parametrize(
    "case_id",
    [
        "bounded:replace:uniform_supported(s=1)",
        "bounded:replace:uniform_domain(s=2)",
        "bounded:replace:insert_nan(s=3)",
        "bounded:replace:insert_inf(s=5)",
        "bounded:replace:insert_large_outliers(s=3)",
        "bounded:replace:insert_shifted_outliers(s=4)",
    ],
)
def test_private_top_k_peeling(case_id, example_data):
    flavors, votes = example_data
    votes = pd.Categorical(votes)
    votes = votes.codes
    votes = np.array(votes).reshape(-1, 1)

    # get the map as well
    candidate_map = {i: name for i, name in enumerate(flavors)}

    auditor = Auditor()

    with auditor:
        output = audited_algorithm.private_top_k_peeling(
            data=votes,
            candidates=candidate_map,
            k=3,
            selection_multiplier=2.0,
            measurement_multiplier=5.0,
        )

    votes_neighbors = generate_neighbors(
        data=votes, strategy="copy_random", rng=42, k=1
    )
    auditor.set_replay()
    # check that indeed the output differs only in one row

    with auditor:
        audited_algorithm.private_top_k_peeling(
            data=votes_neighbors,
            candidates=candidate_map,
            k=3,
            selection_multiplier=2.0,
            measurement_multiplier=5.0,
        )
    auditor.validate_records()

    run_distr_audit = os.getenv("RUN_DISTRIBUTIONAL_AUDIT", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if run_distr_audit:
        auditor.run_distributional_audit(n_samples=100000, epsilon_range=(-25, 25))
        auditor.compute_overall_pld()
        epsilon_rec = auditor.get_overall_current_guarantee(delta=1e-9)
        assert epsilon_rec <= 7.0

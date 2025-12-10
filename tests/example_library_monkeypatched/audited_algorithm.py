import numpy as np
from typing import List, Tuple, Dict, Optional, Union
from .mechanisms import apply_laplace_noise, top_one


def ensure_equality_hook(*args, **kwargs):
    pass


def preprocess_data(raw_data: List[str], candidate_map: List[str]) -> np.ndarray:
    counts = np.zeros(len(candidate_map), dtype=int)

    for item in raw_data:
        counts[item] += 1

    return counts


def postprocess_results(raw_results: List[Tuple[str, float]]) -> List[Dict]:
    processed = []
    for name, score in raw_results:
        clean_score = max(0.0, score)
        processed.append(
            {
                "topic": name,
                "estimated_count": int(round(clean_score)),
                "raw_noisy_value": score,
            }
        )
    return processed


def private_top_k_peeling(
    data: List[str],
    candidates: List[str],
    k: int,
    selection_multiplier: float,
    measurement_multiplier: float,
) -> List[Dict]:
    """
    The Peeling Algorithm:
    1. Select the top item.
    2. Measure its count.
    3. Remove it from the set.
    4. Repeat k times.
    """
    # 1. Preprocessing
    # Transform raw data into a score vector (histogram)
    histogram = preprocess_data(data, candidates)

    # Work on a copy so we don't destroy the original data structures
    current_scores = histogram.astype(float)

    results = []

    for i in range(k):
        winner_idx = top_one(
            q=current_scores,
            l_infinity_sensitivity=1.0,
            noise_multiplier=selection_multiplier,
        )

        winner_name = candidates[winner_idx]

        true_count = histogram[winner_idx]

        noisy_count = apply_laplace_noise(
            values=true_count,
            l1_sensitivity=1.0,
            noise_multiplier=measurement_multiplier,
        )

        results.append((winner_name, noisy_count))
        current_scores[winner_idx] = -np.inf

    final_output = postprocess_results(results)
    ensure_equality(final_output=final_output)
    return final_output

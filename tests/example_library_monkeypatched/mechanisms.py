import opendp.prelude as dp
import numpy as np
from dp_accounting.pld import privacy_loss_distribution
from dp_mechanisms.auditing.audit_primitives import audit_spec
from dp_mechanisms.auditing.metrics import dist_linf
from typing import Optional
from typing import Optional, Union
import numpy as np

from dp_recorder.auditing.audit_primitives import audit_spec


def apply_laplace_noise(
    values: np.ndarray,
    *,
    l1_sensitivity: float,
    noise_multiplier: float,
) -> Union[float, np.ndarray]:
    scale = l1_sensitivity * noise_multiplier
    return values + np.random.laplace(loc=0, scale=scale, size=values.shape)


def top_one(
    q: np.ndarray,
    *,
    l_infinity_sensitivity: float,
    noise_multiplier: float,
):
    scale = l_infinity_sensitivity * noise_multiplier
    noisy_scores = q + np.random.gumbel(loc=0.0, scale=scale, size=q.shape)
    return int(np.argmax(noisy_scores))

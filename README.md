# AGENT_audit

**agent_audit** is a Python library designed to assist in auditing differential privacy mechanisms. It provides a framework for instrumenting code to record execution traces, replaying them with neighboring datasets, and verifying privacy claims through both analytical and empirical methods.

## Features

- **Instrumentation via Decorators**: Easily mark functions as sensitive mechanisms using `@audit_spec`.
- **Record & Replay**: Capture the execution flow of an algorithm and replay it with modified (neighboring) inputs to analyze stability and privacy.
- **Sensitivity Checking**: Validate that the distance between outputs of the same mechanism on neighboring datasets respects the declared sensitivity.
- **Distributional Audit**: Perform empirical privacy audits by running the mechanism many times to estimate the Privacy Loss Distribution (PLD) and resulting Epsilon ($\epsilon$).
- **Trusted Accountant Integration**: Supports analytical PLD computation for trusted components using `dp-accounting`.
- **Equality Assertion**: Ensure that non-sensitive parameters and control flows remain consistent between the record and replay phases.

## Installation

This project is managed with [Poetry](https://python-poetry.org/).

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/oblivious-repos/AGENT_audit.git
    cd AGENT_audit
    ```

2.  **Install dependencies:**
    ```bash
    poetry install
    ```

## Usage

### 1. Instrument Your Code

Use the `@audit_spec` decorator to define your privacy mechanisms. You need to specify the input argument name, the sensitivity parameter (or where to find it), and a metric function.

```python
from agent_audit.auditing.audit_primitives import audit_spec
from agent_audit.auditing.metrics import l1_distance

# Example mechanism
@audit_spec(
    kind="laplace_mechanism",
    input_arg="data",
    sensitivity_arg="sensitivity",
    metric_fn=l1_distance
)
def my_private_mechanism(data, sensitivity, epsilon):
    # Implementation ...
    pass
```

### 2. Run an Audit

The `Auditor` context manager handles the recording and replaying.

```python
from agent_audit.auditing.audit_primitives import Auditor
from agent_audit.auditing.dataset_util import generate_neighbors
import numpy as np

# 1. Setup Data
data = np.array([1.0, 2.0, 3.0])
neighbor_data = generate_neighbors(data, strategy="replace_one", rng=42)

auditor = Auditor()

# 2. Record Phase (Original Data)
with auditor:
    result_d = my_private_mechanism(data=data, sensitivity=1.0, epsilon=1.0)

# 3. Replay Phase (Neighbor Data)
auditor.set_replay()
with auditor:
    result_dp = my_private_mechanism(data=neighbor_data, sensitivity=1.0, epsilon=1.0)

# 4. Validation
# Checks if the distance between inputs (if accessible) matches expectations
# and prepares logs for auditing.
auditor.validate_records()

# 5. Distributional Audit (Optional)
# Runs the mechanism repeatedly to empirically estimate privacy loss.
auditor.run_distributional_audit(n_samples=1000)
auditor.compute_overall_pld()
epsilon_empirical = auditor.get_overall_current_guarantee(delta=1e-5)

print(f"Empirical Epsilon: {epsilon_empirical}")
```

## Project Structure

- `src/agent_audit/auditing/`: Core components.
    - `audit_primitives.py`: The `Auditor` class and `@audit_spec` decorator.
    - `metrics.py`: Distance metrics (L1, L2, etc.).
    - `dataset_util.py`: Helpers for generating neighboring datasets.
    - `privacy_converter.py` & `pld_from_epsilon_delta.py`: Utilities for converting between privacy profiles and PLDs.
- `src/agent_audit/visualization/`: Tools for visualizing audit results.
- `tests/`: Unit and integration tests demonstrating usage.

## Development

To run tests:

```bash
poetry run pytest
```

To run tests with distributional audit enabled (slower):

```bash
RUN_DISTRIBUTIONAL_AUDIT=true poetry run pytest
```

## Technical report and citation:

The technical report introducing AGENT_audit, presenting its design principles, mathematical foundations, and benchmarks can be found here: #TODO: add when available online.

Consider citing AGENT_audit if you use it in your papers, as follows:

```bibtex
TODO
```
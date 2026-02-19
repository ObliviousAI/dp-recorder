# dp-recorder

**dp-recorder** is a Python library for **gray-box auditing** of Differential Privacy (DP) libraries. It implements the **Re:cord-play** framework, designed to detect implementation bugs, sensitivity miscalculations, and data-dependent control flow leaks in DP algorithms.

Unlike traditional black-box auditing, `dp-recorder` inspects the internal state of the algorithm. It can deterministically flag privacy violations in a single pair of executions or perform targeted statistical auditing on specific components.

## 🚀 Key Features

* **Gray-Box Inspection**: Instruments the code to inspect internal inputs to privacy mechanisms (e.g., Laplace, Gaussian) rather than just final outputs.
* **Re:cord-play (Deterministic Testing)**: Captures execution traces on dataset $D$ and replays them on neighbor $D'$. It "freezes" mechanism outputs to verify that all surrounding control flow remains **invariant** (data-independent).
* **Sensitivity Verification**: Automatically verifies that the distance between inputs to privacy primitives does not exceed the declared sensitivity ($\Delta_{actual} \leq \Delta_{declared}$).
* **Re:cord-play-sample (Statistical Auditing)**: For untrusted or custom primitives, the tool isolates the component and runs a targeted distributional audit (estimating PLDs) without re-running the heavy pre-processing logic.
* **Hybrid Composition**: Seamlessly mix trusted primitives (analytical PLDs) with untrusted components (empirical PLDs) to get an end-to-end privacy guarantee.
* **CI/CD Ready**: Designed to run as a fast unit test within standard development pipelines.

## 📦 Installation

This project is managed with [Poetry](https://python-poetry.org/).

```bash
git clone https://github.com/oblivious-repos/dp-recorder.git
cd dp-recorder
poetry install
```

### 🧠 How It Works

The framework operates on the insight that DP algorithms interleave **data-dependent** calls (privacy mechanisms) with **data-independent** logic (pre-processing, control flow).

1. **Phase 1 (Record):** Run algorithm on dataset $D$. Record all inputs/outputs of DP primitives and snapshot the PRNG state.

2. **Phase 2 (Replay):** Run algorithm on neighbor $D'$.
    * **Freeze Outputs:** Force DP primitives to return the *exact same outputs* as Phase 1.
    * **Check Invariance:** Since mechanism outputs are identical, the program state should not diverge. If it does, **private data has leaked** into the control flow.
    * **Check Sensitivity:** Measure the empirical distance between inputs $q(D)$ and $q(D')$. If it exceeds the sensitivity declared by the developer, a bug is flagged.

### 🛠 Usage

**1. Instrument Your Primitives**

Use `@audit_spec` to mark functions that add noise. If you want to verify that specific variables (like hyperparameters or data shapes) do not depend on private data, use `ensure_equality`.

```python
from dp_recorder.auditing.audit_primitives import audit_spec, ensure_equality
from dp_recorder.auditing.metrics import l1_distance

# A trusted primitive (we verify inputs, but trust the noise generation)
@audit_spec(
    kind="laplace_mechanism",
    input_arg="data",
    sensitivity_arg="sensitivity",
    metric_fn=l1_distance
)
def laplace_mechanism(data, sensitivity, epsilon):
    # Standard implementation...
    return data + np.random.laplace(0, sensitivity / epsilon, size=data.shape)

# Your complex DP algorithm
def dp_algorithm(private_data, epsilon):
    # 1. Pre-processing
    # We must ensure params derived here don't leak privacy
    clipping_bound = 10.0

    # 2. Invariance Check
    # Explicitly assert that this variable must be identical across neighbors
    ensure_equality(clipping_bound, name="clipping_bound")

    # 3. Mechanism Call
    clipped_data = np.clip(private_data, 0, clipping_bound)
    return laplace_mechanism(data=clipped_data, sensitivity=clipping_bound, epsilon=epsilon)
```

### 2. Run the Auditor

The `Auditor` manages the "Record" and "Replay" phases.

```python
from dp_recorder.auditing.audit_primitives import Auditor
from dp_recorder.auditing.dataset_util import generate_neighbors
import numpy as np

# 1. Setup Data
data = np.array([1.0, 2.0, 3.0, 100.0]) # Contains an outlier
neighbor_data = generate_neighbors(data, strategy="replace_one", rng=42)

auditor = Auditor()

# 2. Phase 1: Record (Original Data)
auditor.set_record()
with auditor:
    # Run the algo. Traces are saved internally.
    result_d = dp_algorithm(data, epsilon=1.0)

# 3. Phase 2: Replay (Neighbor Data)
auditor.set_replay()
with auditor:
    # Outputs of mechanisms are frozen to match Phase 1.
    # If control flow diverges here, Auditor raises an InvarianceError.
    result_dp = dp_algorithm(neighbor_data, epsilon=1.0)

# 4. Deterministic Validation
# Checks if empirical input sensitivity <= declared sensitivity.
# This catches bugs like "forgot to clip" or "wrong sensitivity formula".
try:
    auditor.validate_records()
    print("✅ Deterministic checks passed.")
except Exception as e:
    print(f"❌ Privacy Violation Detected: {e}")

# 5. (Optional) Distributional Audit
# If you have custom primitives without known accounting,
# run statistical tests on those specific components.
auditor.run_distributional_audit(n_samples=10000)
auditor.compute_overall_pld()
```

### Project Structure

* `src/dp_recorder/`
    * `auditing/audit_primitives.py`: Core `Auditor` class and instrumentation hooks.
    * `auditing/metrics.py`: Distance metrics ($L_1, L_2, L_\infty$) for sensitivity checks.
    * `auditing/dataset_util.py`: Strategies for generating neighboring datasets (Add/Remove, Replace-one).
    * `auditing/pld_*`: Integration with `dp-accounting` for hybrid composition.
* `tests/`: Integration tests reproducing real-world bugs found in libraries like Opacus, SmartNoise, and Diffprivlib.

### Development

To run the fast, deterministic test suite:

```bash
poetry run pytest
```

To run the slower, statistical test suite:

```bash
RUN_DISTRIBUTIONAL_AUDIT=true poetry run pytest
```

### Citation

If you use dp-recorder (Re:cord-play) in your research or workflows, please cite the following paper:

```bibtex
@inproceedings{recordplay2025,
  title={Privacy in Theory, Bugs in Practice: A Grey-Box Auditing Framework of Differential Privacy Libraries},
  author={Tudor Cebere, David Erb, Damien Desfontaines, Aurélien Bellet and Jack Fitzimons},
  booktitle={TODO},
  year={2025},
}
```

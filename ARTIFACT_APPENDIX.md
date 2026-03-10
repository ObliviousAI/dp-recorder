# Artifact Appendix

Paper title: **Privacy in Theory, Bugs in Practice: Grey-Box Auditing of Differential Privacy Libraries**

Requested Badge(s):
  - [x] **Available**
  - [x] **Functional**
  - [x] **Reproduced**

## Description

1. Paper: Cebere, T., Erb, D., Bellet, A., Desfontaines, D., Fitzsimons, J. (2026). Privacy in Theory, Bugs in Practice: Grey-Box Auditing of Differential Privacy Libraries. *Proceedings on Privacy Enhancing Technologies*.
2. Artifact: The artifact is `dp-recorder`, an open-source Python framework implementing the `Re:cord-play` and `Re:cord-play-sample` paradigms for the gray-box auditing of Differential Privacy mechanisms. It provides the core instrumentation to record and replay internal states of DP algorithms. This artifact directly supports the paper by demonstrating how deterministic and statistical tests successfully flag real-world implementation bugs, sensitivity miscalculations, and data-dependent control flow leaks. 

### Security/Privacy Issues and Ethical Concerns

The artifact does not disable any security mechanisms or run inherently vulnerable or malicious code on the host machine. It is a testing framework that operates locally using simulated mock functions to represent logic bugs found in the wild. There are no ethical concerns, as the framework uses entirely synthetic, auto-generated NumPy arrays for testing and does not interact with any real personal data.

## Basic Requirements

### Hardware Requirements

1. Can run on a laptop (No special hardware requirements). Computations for distributional audits (`Re:cord-play-sample`) may benefit from modern multi-core processors, but are not strictly required.
2. The experiments reported in the paper were executed on standard consumer-grade CPUs (16GB RAM).

### Software Requirements

1. **OS:** Cross-platform (Linux, macOS, Windows). Developed and tested on Ubuntu 22.04.
2. **OS Packages:** `git` (to clone the repository) and standard build tools (e.g., `build-essential` on Ubuntu).
3. **Artifact packaging:** Docker 24.0+ is heavily encouraged to run the provided Dockerfile and isolate dependencies cleanly.
4. **Programming Language:** Python >= 3.10.
5. **Dependencies:** Managed via Poetry (`pyproject.toml`). Key packages include `numpy`, `pandas`, `scipy`, `scikit-learn`, `dp-accounting`, and `pytest`.
6. **Machine Learning Models:** None required.
7. **Datasets:** None required. All tests utilize low-dimensional synthetic arrays generated on the fly.

### Estimated Time and Storage Consumption

- **Time:** ~5 human-minutes for setup. Each deterministic experiment takes < 1 compute-minute. The statistical audit experiment takes  less than 10 compute-minutes.
- **Storage:** < 100 MB of disk space for the repository. Environment dependencies and the Docker image will require roughly ~1 GB.

## Environment

### Accessibility

The artifact can be accessed via the persistent GitHub repository at:
https://github.com/ObliviousAI/dp-recorder


### Set up the environment

Clone the repository and build the provided Docker image to isolate the Python/Poetry dependencies:

```bash
git clone git@github.com:ObliviousAI/dp-recorder.git
cd dp-recorder
docker build -t dp-recorder:latest .

```

### Testing the Environment

To verify that the environment is set up correctly and the deterministic auditing primitives function as expected, launch the Docker container interactively, mounting the current directory as a volume, and run the basic Laplace test:

```bash
docker run --rm -it -v ${PWD}:/workspaces/dp-recorder \
    -w /workspaces/dp-recorder \
    --entrypoint bash dp-recorder:latest

# Inside the container, run:
poetry run pytest

```

**Expected output:** The tests should pass.

## Artifact Evaluation

### Main Results and Claims

#### Main Result 1: Structural Verification (Re:cord-play)

Our paper claims that structural bugs—such as Invariance Violations (e.g., data-dependent control flow or dataset size leaks) and Sensitivity Miscalibrations—can be caught deterministically by freezing privacy primitives and enforcing structural invariants across adjacent datasets (Section 3.2 and Section 4.3). This is supported by our deterministic test suite (`test_buggy_private_mean.py`, `test_domain_inference.py`, `test_sensitivity_miscalibration.py`), which replicates the buggy code structures found in Diffprivlib, SmartNoise, Opacus, and Synthcity.

#### Main Result 2: Statistical Verification of Accounting (Re:cord-play-sample)

Our paper claims that `Re:cord-play-sample` can identify improper budget composition statistically by sampling isolated execution traces to estimate empirical Privacy Loss Distributions (PLDs) (Section 3.3). This is supported by `test_double_spending.py, test_noise_miscalibration.py`, which reproduces the accounting bugs found in libraries like MOSTLY AI.

### Experiments

#### Experiment 1: Control Flow Leak / Domain Inference Detection

* **Time:** 1 human-minute + < 1 compute-minute.
* **Storage:** Negligible.

This experiment reproduces the deterministic detection of data-dependent control flow leaks (Main Result 1). It executes two Minimal Reproducible Examples (MREs) representing real-world bugs:

1. `test_buggy_private_mean.py`: Simulates the Opacus bug where dataset size (`len(data)`) leaks into the public control flow as a scaling factor.
2. `test_domain_inference.py`: Simulates the Diffprivlib and dpmm bug where class domains are inferred dynamically from private data via `np.unique(data)`.

Run the following command:

```bash
pytest tests/test_buggy_private_mean.py tests/test_domain_inference.py -v

```

**Expected Result:** The tests execute rapidly and purposefully raise `AssertionError`s signaling an invariance violation. The `ensure_equality` hook intercepts the parameters (`n` or `num_classes`) and accurately flags that they diverged between the recorded execution on dataset $D$ and the replay execution on the neighbor dataset $D'$. `pytest` will report these tests as **PASSED** (green text) because the framework successfully caught the vulnerabilities.

#### Experiment 2: Sensitivity Miscalibration, Noise Miscalibration & Pathological Inputs

* **Time:** 1 human-minute + < 1 compute-minute.
* **Storage:** Negligible.

This experiment tests the framework's ability to deterministically catch improper inputs passed to privacy primitives (Main Result 1). It executes three MREs:

1. `test_sensitivity_miscalibration.py`: Simulates the SmartNoise SDK bug where the algorithm sums raw, unclipped data but declares the sensitivity of clipped data.
2. `test_noise_miscalibration.py`: Simulates the Synthcity PrivBayes bug where specific hyperparameters evaluate the theoretical sensitivity to zero, entirely disabling privacy.
3. `test_nan_injection.py`: Demonstrates the vulnerability outlined in Section 4.3.9 where `np.nan` values silently bypass standard `np.clip` operations. Our framework's robust `dist_l1` metric intelligently traps `NaN` mathematical evasions by translating them to an infinite distance.

Run the following command:

```bash
pytest tests/test_sensitivity_miscalibration.py tests/test_noise_miscalibration.py tests/test_nan_injection.py -v

```

**Expected Result:** In all three cases, the framework computes the empirical input distance and finds it strictly greater than the declared sensitivity. It deterministically throws a Sensitivity Miscalibration `AssertionError` stopping the execution. `pytest` will report these tests as **PASSED**, confirming the framework successfully intercepted the programmatic errors.

#### Experiment 3: Double Spending / Accounting Bug Detection

* **Time:** 1 human-minute + 1-3 compute-minutes.
* **Storage:** Negligible.

This experiment reproduces the statistical auditing engine (`Re:cord-play-sample`) evaluating a mechanism that applies two DP queries while assuming it only consumed the budget of one (Main Result 2), which is representative of the MOSTLY AI bug.

Run the following command (`-s` ensures the empirical epsilon prints to the console):

```bash
pytest tests/test_double_spending.py -v -s

```

**Expected Result:**  The framework isolates the trace and generates 10,000 samples to compute the real empirical Privacy Loss Distribution (`run_distributional_audit`). It will correctly output that the empirical Epsilon is significantly higher than the target Epsilon (e.g., `Target Epsilon: 1.0 | Empirical Epsilon: 1.98`), triggering an `AssertionError` stating: "Privacy budget exceeded!". `pytest` will report the test as **PASSED**, validating the statistical accounting module.

## Limitations

Omission of Vulnerable Third-Party Libraries:
Our evaluation in Section 4 of the paper audited 12 diverse, large-scale open-source DP libraries (e.g., PyTorch-based Opacus, IBM's Diffprivlib, Microsoft's SmartNoise, Google DeepMind's JAX-privacy, Spark-based systems). We deliberately do not package the full vulnerable source code of these 12 frameworks in our artifact.

Attempting to package historical, vulnerable versions of 12 distinct ecosystems—which require specific, mutually conflicting and outdated versions of heavy frameworks like PyTorch, JAX, and Scikit-learn—would lead to an excessively bloated, brittle artifact. It would be virtually impossible to reproduce reliably in a single container and would inevitably fail due to dependency issues. Furthermore, the core scientific contribution of our work is the **`dp-recorder` auditing framework**, not the vulnerable code it audited.

To ensure functional reproducibility, we have rigorously translated the exact logic flaws from those libraries into Minimal Reproducible Examples (MREs) within our test suite, to actually guide practitioners on how to instantiate our framework to catch this family of issues. We distilled the structural flaws (e.g., the Diffprivlib `np.unique(y)` domain leak, the Opacus `len(data)` leak, the SmartNoise clipping omission) into self-contained test functions. This allows reviewers to cleanly verify that our framework deterministically catches these specific classes of bugs.

To validate the empirical claims that these bugs existed in the real world (for the **Reproduced** badge), we rely on the public, independently verifiable PRs and issue trackers where the maintainers acknowledged and patched the flaws based on our reports. Reviewers can verify the exact commit hashes audited in **Table 2** of our paper for the code. Furthermore, we provide links to the merged GitHub PRs and Issues in our repository documentation as undeniable ground-truth evidence. Until now, here are the patched repositories:
* https://github.com/sassoftware/dpmm/issues/18
* https://github.com/ryan112358/mbi/issues/65
* https://github.com/opendp/smartnoise-sdk/issues/622
* https://github.com/opendp/smartnoise-sdk/issues/621

The diffprivlib issues were also confirmed but not yet patched.

## Notes on Reusability

The `dp-recorder` library is designed as a general framework meant to be integrated into standard CI/CD pipelines as a "privacy debugger." Developers can easily adapt it to audit their own DP libraries or algorithms by simply annotating their core noise-adding primitives with our `@audit_spec` decorator and applying `ensure_equality` hooks for invariant control flow values. The underlying PLD estimation connects seamlessly to standard `dp-accounting` routines, allowing the integration of custom mechanisms into a hybrid composition framework with minimal boilerplate code. Because the tool is agnostic to the mathematical definition of dataset adjacency, it can also easily be extended to support custom metrics.ithms. This artifact directly supports the paper by demonstrating how deterministic and statistical tests successfully flag real-world implementation bugs, sensitivity miscalculations, and data-dependent control flow leaks. 

### Security/Privacy Issues and Ethical Concerns

The artifact does not disable any security mechanisms or run inherently vulnerable or malicious code on the host machine. It is a testing framework that operates locally using simulated mock functions to represent logic bugs found in the wild. There are no ethical concerns, as the framework uses entirely synthetic, auto-generated NumPy arrays for testing and does not interact with any real personal data.

## Basic Requirements

### Hardware Requirements

1. Can run on a laptop (No special hardware requirements). Computations for distributional audits (`Re:cord-play-sample`) may benefit from modern multi-core processors, but are not strictly required.
2. The experiments reported in the paper were executed on standard consumer-grade CPUs (16GB RAM).

### Software Requirements

1. **OS:** Cross-platform (Linux, macOS, Windows). Developed and tested on Ubuntu 22.04.
2. **OS Packages:** `git` (to clone the repository) and standard build tools (e.g., `build-essential` on Ubuntu).
3. **Artifact packaging:** Docker 24.0+ is heavily encouraged to run the provided Dockerfile and isolate dependencies cleanly.
4. **Programming Language:** Python >= 3.10.
5. **Dependencies:** Managed via Poetry (`pyproject.toml`). Key packages include `numpy`, `pandas`, `scipy`, `scikit-learn`, `dp-accounting`, and `pytest`.
6. **Machine Learning Models:** None required.
7. **Datasets:** None required. All tests utilize low-dimensional synthetic arrays generated on the fly.

### Estimated Time and Storage Consumption

- **Time:** ~5 human-minutes for setup. Each deterministic experiment takes < 1 compute-minute. The statistical audit experiment takes  less than 10 compute-minutes.
- **Storage:** < 100 MB of disk space for the repository. Environment dependencies and the Docker image will require roughly ~1 GB.

## Environment

### Accessibility

The artifact can be accessed via the persistent GitHub repository at:
https://github.com/oblivious-repos/dp-recorder/tree/main


### Set up the environment

Clone the repository and build the provided Docker image to isolate the Python/Poetry dependencies:

```bash
git clone [https://github.com/oblivious-repos/dp-recorder.git](https://github.com/oblivious-repos/dp-recorder.git)
cd dp-recorder
docker build -t dp-recorder:latest .

```

### Testing the Environment

To verify that the environment is set up correctly and the deterministic auditing primitives function as expected, launch the Docker container interactively, mounting the current directory as a volume, and run the basic Laplace test:

```bash
docker run --rm -it -v ${PWD}:/workspaces/dp-recorder \
    -w /workspaces/dp-recorder \
    --entrypoint bash dp-recorder:latest

# Inside the container, run:
poetry run pytest

```

**Expected output:**
The test should pass (e.g., `1 passed in 0.05s`), confirming that the `instrumented_laplace` mechanism operates correctly and is properly hooked by the `@audit_spec` decorator.

## Artifact Evaluation

### Main Results and Claims

#### Main Result 1: Structural Verification (Re:cord-play)

Our paper claims that structural bugs—such as Invariance Violations (e.g., data-dependent control flow or dataset size leaks) and Sensitivity Miscalibrations—can be caught deterministically by freezing privacy primitives and enforcing structural invariants across adjacent datasets (Section 3.2 and Section 4.3). This is supported by our deterministic test suite (`test_buggy_private_mean.py`, `test_domain_inference.py`, `test_sensitivity_miscalibration.py`), which replicates the buggy code structures found in Diffprivlib, SmartNoise, Opacus, and Synthcity.

#### Main Result 2: Statistical Verification of Accounting (Re:cord-play-sample)

Our paper claims that `Re:cord-play-sample` can identify improper budget composition statistically by sampling isolated execution traces to estimate empirical Privacy Loss Distributions (PLDs) (Section 3.3). This is supported by `test_double_spending.py, test_noise_miscalibration.py`, which reproduces the accounting bugs found in libraries like MOSTLY AI.

### Experiments

#### Experiment 1: Control Flow Leak / Domain Inference Detection

* **Time:** 1 human-minute + < 1 compute-minute.
* **Storage:** Negligible.

This experiment reproduces the deterministic detection of data-dependent control flow leaks (Main Result 1). It executes two Minimal Reproducible Examples (MREs) representing real-world bugs:

1. `test_buggy_private_mean.py`: Simulates the Opacus bug where dataset size (`len(data)`) leaks into the public control flow as a scaling factor.
2. `test_domain_inference.py`: Simulates the Diffprivlib and dpmm bug where class domains are inferred dynamically from private data via `np.unique(data)`.

Run the following command:

```bash
pytest tests/test_buggy_private_mean.py tests/test_domain_inference.py -v

```

**Expected Result:** The tests execute rapidly and purposefully raise `AssertionError`s signaling an invariance violation. The `ensure_equality` hook intercepts the parameters (`n` or `num_classes`) and accurately flags that they diverged between the recorded execution on dataset $D$ and the replay execution on the neighbor dataset $D'$. `pytest` will report these tests as **PASSED** (green text) because the framework successfully caught the vulnerabilities.

#### Experiment 2: Sensitivity Miscalibration, Noise Miscalibration & Pathological Inputs

* **Time:** 1 human-minute + < 1 compute-minute.
* **Storage:** Negligible.

This experiment tests the framework's ability to deterministically catch improper inputs passed to privacy primitives (Main Result 1). It executes three MREs:

1. `test_sensitivity_miscalibration.py`: Simulates the SmartNoise SDK bug where the algorithm sums raw, unclipped data but declares the sensitivity of clipped data.
2. `test_noise_miscalibration.py`: Simulates the Synthcity PrivBayes bug where specific hyperparameters evaluate the theoretical sensitivity to zero, entirely disabling privacy.
3. `test_nan_injection.py`: Demonstrates the vulnerability outlined in Section 4.3.9 where `np.nan` values silently bypass standard `np.clip` operations. Our framework's robust `dist_l1` metric intelligently traps `NaN` mathematical evasions by translating them to an infinite distance.

Run the following command:

```bash
pytest tests/test_sensitivity_miscalibration.py tests/test_noise_miscalibration.py tests/test_nan_injection.py -v

```

**Expected Result:** In all three cases, the framework computes the empirical input distance and finds it strictly greater than the declared sensitivity. It deterministically throws a Sensitivity Miscalibration `AssertionError` stopping the execution. `pytest` will report these tests as **PASSED**, confirming the framework successfully intercepted the programmatic errors.

#### Experiment 3: Double Spending / Accounting Bug Detection

* **Time:** 1 human-minute + 1-3 compute-minutes.
* **Storage:** Negligible.

This experiment reproduces the statistical auditing engine (`Re:cord-play-sample`) evaluating a mechanism that applies two DP queries while assuming it only consumed the budget of one (Main Result 2), which is representative of the MOSTLY AI bug.

Run the following command (`-s` ensures the empirical epsilon prints to the console):

```bash
pytest tests/test_double_spending.py -v -s

```

**Expected Result:**  The framework isolates the trace and generates 10,000 samples to compute the real empirical Privacy Loss Distribution (`run_distributional_audit`). It will correctly output that the empirical Epsilon is significantly higher than the target Epsilon (e.g., `Target Epsilon: 1.0 | Empirical Epsilon: 1.98`), triggering an `AssertionError` stating: "Privacy budget exceeded!". `pytest` will report the test as **PASSED**, validating the statistical accounting module.

## Limitations

Omission of Vulnerable Third-Party Libraries:
Our evaluation in Section 4 of the paper audited 12 diverse, large-scale open-source DP libraries (e.g., PyTorch-based Opacus, IBM's Diffprivlib, Microsoft's SmartNoise, Google DeepMind's JAX-privacy, Spark-based systems). We deliberately do not package the full vulnerable source code of these 12 frameworks in our artifact.

Attempting to package historical, vulnerable versions of 12 distinct ecosystems—which require specific, mutually conflicting and outdated versions of heavy frameworks like PyTorch, JAX, and Scikit-learn—would lead to an excessively bloated, brittle artifact. It would be virtually impossible to reproduce reliably in a single container and would inevitably fail due to dependency issues. Furthermore, the core scientific contribution of our work is the **`dp-recorder` auditing framework**, not the vulnerable code it audited.

To ensure functional reproducibility, we have rigorously translated the exact logic flaws from those libraries into Minimal Reproducible Examples (MREs) within our test suite, to actually guide practitioners on how to instantiate our framework to catch this family of issues. We distilled the structural flaws (e.g., the Diffprivlib `np.unique(y)` domain leak, the Opacus `len(data)` leak, the SmartNoise clipping omission) into self-contained test functions. This allows reviewers to cleanly verify that our framework deterministically catches these specific classes of bugs.

To validate the empirical claims that these bugs existed in the real world (for the **Reproduced** badge), we rely on the public, independently verifiable PRs and issue trackers where the maintainers acknowledged and patched the flaws based on our reports. Reviewers can verify the exact commit hashes audited in **Table 2** of our paper for the code. Furthermore, we provide links to the merged GitHub PRs and Issues in our repository documentation as undeniable ground-truth evidence. Until now, here are the patched repositories:
* https://github.com/sassoftware/dpmm/issues/18
* https://github.com/ryan112358/mbi/issues/65
* https://github.com/opendp/smartnoise-sdk/issues/622
* https://github.com/opendp/smartnoise-sdk/issues/621

The diffprivlib issues were also confirmed but not yet patched.

## Notes on Reusability

The `dp-recorder` library is designed as a general framework meant to be integrated into standard CI/CD pipelines as a "privacy debugger." Developers can easily adapt it to audit their own DP libraries or algorithms by simply annotating their core noise-adding primitives with our `@audit_spec` decorator and applying `ensure_equality` hooks for invariant control flow values. The underlying PLD estimation connects seamlessly to standard `dp-accounting` routines, allowing the integration of custom mechanisms into a hybrid composition framework with minimal boilerplate code. Because the tool is agnostic to the mathematical definition of dataset adjacency, it can also easily be extended to support custom metrics.
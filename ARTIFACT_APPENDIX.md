# Artifact Appendix

Paper title: **Privacy in Theory, Bugs in Practice: Grey-Box Auditing of Differential Privacy Libraries**

Requested Badge(s):
  - [x] **Available**
  - [x] **Functional**
  - [x] **Reproduced**

## Description

1. Paper: Cebere, T., Erb, D., Bellet, A., Desfontaines, D., Fitzsimons, J. (2026). Privacy in Theory, Bugs in Practice: Grey-Box Auditing of Differential Privacy Libraries. *Proceedings on Privacy Enhancing Technologies*.
2. Artifact: The artifact is `dp-recorder`, an open-source Python framework implementing the `Re:cord-play` and `Re:cord-play-sample` paradigms for the gray-box auditing of Differential Privacy mechanisms. It provides the core instrumentation to record and replay internal states of DP algorithms. This artifact directly supports the paper by demonstrating how deterministic and statistical tests successfully flag real-world implementation bugs, sensitivity miscalculations, and data-dependent control flow leaks. In addition to the lightweight Minimal Reproducible Examples (MREs) in `tests/`, the artifact includes a containerized audit harness for three instrumented real-world library examples in `tests/audit_harness/submissions/pets_submission.zip`.

### Security/Privacy Issues and Ethical Concerns

The artifact does not disable any security mechanisms or run malicious code on the host machine. The core test suite operates locally using synthetic, auto-generated NumPy arrays. The real-world audit harness intentionally executes instrumented snapshots of public open-source libraries with known privacy bugs, but it does so inside Docker containers and uses only bundled test fixtures or generated data. No external personal data is downloaded or required.

## Basic Requirements

### Hardware Requirements

1. Can run on a laptop (No special hardware requirements). Computations for distributional audits (`Re:cord-play-sample`) may benefit from modern multi-core processors, but are not strictly required.
2. The experiments reported in the paper were executed on standard consumer-grade CPUs (16GB RAM).

### Software Requirements

1. **OS:** Cross-platform (Linux, macOS, Windows). Developed and tested on Ubuntu 22.04.
2. **OS Packages:** `git` (to clone the repository) and standard build tools (e.g., `build-essential` on Ubuntu).
3. **Artifact packaging:** Docker 24.0+ is heavily encouraged for the core artifact and required for the real-world library audit harness.
4. **Programming Language:** Python >= 3.10.
5. **Dependencies:** Managed via Poetry (`pyproject.toml`). Key packages include `numpy`, `pandas`, `scipy`, `scikit-learn`, `dp-accounting`, and `pytest`.
6. **Machine Learning Models:** None required.
7. **Datasets:** No external datasets are required. The core tests utilize low-dimensional synthetic arrays generated on the fly; the real-world audit harness uses files bundled inside `tests/audit_harness/submissions/pets_submission.zip`.

### Estimated Time and Storage Consumption

- **Time:** ~5 human-minutes for setup. Each deterministic experiment takes < 1 compute-minute. The statistical audit experiment takes less than 10 compute-minutes. The containerized real-world library harness takes roughly 15-45 minutes to build and execute, depending on local hardware, Docker cache state, and network speed.
- **Storage:** < 100 MB of disk space for the repository, excluding Docker layers. The real-world submission zip is about 5.7 MB. Docker images and dependency caches require additional local storage.

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

#### Experiment 4: Containerized Real-World Library Audits

* **Time:** 1 human-minute + 15-45 compute-minutes.
* **Storage:** The bundled submission zip is about 5.7 MB; Docker layers and dependency caches require additional local storage.

This experiment runs the three packaged real-world library examples that we instrumented after finding bugs: `dpmm`, `mbi`, and `synthcity`. The implementation and audit suites are stored in:

```text
tests/audit_harness/submissions/pets_submission.zip
```

Inside the zip file, each library has a dedicated folder containing instrumented source code and an associated `tests/` directory containing the audit implementation:

```text
pets_submission/
  examples/
    dpmm_auditing/
      dpmm/
      tests/
    mbi_auditing/
      mbi/
      tests/
    synthcity_auditing/
      synthcity/
      tests/
```

The instrumentation uses inlined auditing wrappers around the libraries' privacy primitives and heavily uses equality hooks for values that must remain invariant across record/replay executions. For example, the real-world examples include audited Gaussian mechanisms of the following form:

```python
def gaussian_pld(
    l2_sensitivity: float,
    epsilon: Optional[float] = None,
    scale: Optional[float] = None,
    delta: Optional[float] = None,
) -> privacy_loss_distribution.PrivacyLossDistribution:
    if scale is None:
        raise ValueError("gaussian_pld requires scale (standard deviation of the noise)")
    return privacy_loss_distribution.from_gaussian_mechanism(
        standard_deviation=scale,
        value_discretization_interval=1e-4,
    )

@audit_spec(
    kind="GM",
    input_arg="values",
    sensitivity_arg="l2_sensitivity",
    metric_fn=dist_l2,
    accountant=gaussian_pld,
)
def apply_gaussian_noise(
    values: np.ndarray,
    *,
    l2_sensitivity: float,
    scale: float = None,
) -> Union[float, np.ndarray]:
    ...
```

To make evaluation reproducible, `tests/audit_harness/run_all.sh` builds a dedicated Docker image, unzips the submission, provisions isolated `PYTHONPATH` settings for each library, runs all manifests in parallel, and prints a summary report. From the repository root, run:

```bash
python3 -m pip install rich  # optional, enables live progress output
bash tests/audit_harness/run_all.sh
```

If `rich` is not installed in the host Python environment, the harness falls back to plain text monitoring.

Depending on hardware, Docker cache state, and network speed, the full suite takes roughly 15-45 minutes to build and execute. The current harness reports the discovered audit violations as pytest failures, so the command may exit non-zero even when the audit successfully catches the intended bugs. The summary report is the success criterion.

**Expected output:** The harness prints a manifest-level summary. The 24 `Fail` entries below are expected: they represent successful interventions by the audit harness, catching edge cases, sensitivity violations, and structural mismatches in the target libraries.

```text
Manifest                        Library         Pass  XFail  XPass  Fail   Err  Status
--------------------------------------------------------------------------------------------------------------
  dpmm.json                         dpmm               7      0      0    11     0  FAIL
  mbi.json                          mbi               32      0      0     8     0  FAIL
  synthcity.json                    synthcity         10      0      0     5     0  FAIL
--------------------------------------------------------------------------------------------------------------
  TOTAL                                               49      0      0    24     0

Failed tests (24):

  1. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:add:copy_random(s=0)]
  2. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:remove:randidx(s=1)]
  3. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:add:insert_nan(s=2)]
  4. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:add:insert_inf(s=5)]
  5. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:add:insert_large_outliers(s=3)]
  6. [dpmm] examples.dpmm_auditing.tests.test_aim_audit::test_dpmm_aim_record_replay_hooks[4-unbounded:add:insert_shifted_outliers(s=4)]
  7. [dpmm] examples.dpmm_auditing.tests.test_priv_bayes_audit::test_dpmm_priv_bayes_record_replay_hooks[unbounded:add:copy_random(s=0)]
  8. [dpmm] examples.dpmm_auditing.tests.test_priv_bayes_audit::test_dpmm_priv_bayes_record_replay_hooks[unbounded:add:insert_nan(s=2)]
  9. [dpmm] examples.dpmm_auditing.tests.test_priv_bayes_audit::test_dpmm_priv_bayes_record_replay_hooks[unbounded:add:insert_inf(s=5)]
  10. [dpmm] examples.dpmm_auditing.tests.test_priv_bayes_audit::test_dpmm_priv_bayes_record_replay_hooks[unbounded:add:insert_large_outliers(s=3)]
  11. [dpmm] examples.dpmm_auditing.tests.test_priv_bayes_audit::test_dpmm_priv_bayes_record_replay_hooks[unbounded:add:insert_shifted_outliers(s=4)]
  12. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[3-5.0-bounded:replace-fake]
  13. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[3-5.0-bounded:replace-adult]
  14. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[3-10.0-bounded:replace-fake]
  15. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[3-10.0-bounded:replace-adult]
  16. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[5-5.0-bounded:replace-fake]
  17. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[5-5.0-bounded:replace-adult]
  18. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[5-10.0-bounded:replace-fake]
  19. [mbi] examples.mbi_auditing.tests.test_jam_mbi_audit::test_jam_mbi_audit[5-10.0-bounded:replace-adult]
  20. [synthcity] examples.synthcity_auditing.tests.test_privbayes_audit::test_privbayes_record_replay_hooks[1.0-fake-bounded:replace:uniform_domain(s=2)]
  21. [synthcity] examples.synthcity_auditing.tests.test_privbayes_audit::test_privbayes_record_replay_hooks[1.0-fake-bounded:replace:insert_nan(s=3)]
  22. [synthcity] examples.synthcity_auditing.tests.test_privbayes_audit::test_privbayes_record_replay_hooks[1.0-fake-bounded:replace:insert_inf(s=5)]
  23. [synthcity] examples.synthcity_auditing.tests.test_privbayes_audit::test_privbayes_record_replay_hooks[1.0-fake-bounded:replace:insert_large_outliers(s=3)]
  24. [synthcity] examples.synthcity_auditing.tests.test_privbayes_audit::test_privbayes_record_replay_hooks[1.0-fake-bounded:replace:insert_shifted_outliers(s=4)]
```

Full pytest logs are generated automatically and can be reviewed in:

```text
tests/audit_harness/results/<library>.log
```

## Limitations

Omission of Vulnerable Third-Party Libraries:
Our evaluation in Section 4 of the paper audited 12 diverse, large-scale open-source DP libraries (e.g., PyTorch-based Opacus, IBM's Diffprivlib, Microsoft's SmartNoise, Google DeepMind's JAX-privacy, Spark-based systems). The artifact packages a reproducible Docker harness for three representative real-world examples (`dpmm`, `mbi`, and `synthcity`) in `tests/audit_harness/submissions/pets_submission.zip`, but it deliberately does not package the full vulnerable source code for all 12 audited frameworks.

Attempting to package historical, vulnerable versions of all 12 distinct ecosystems—which require specific, mutually conflicting and outdated versions of heavy frameworks like PyTorch, JAX, and Scikit-learn—would lead to an excessively bloated, brittle artifact. It would be virtually impossible to reproduce reliably in a single container and would inevitably fail due to dependency issues. Furthermore, the core scientific contribution of our work is the **`dp-recorder` auditing framework**, not the vulnerable code it audited.

To ensure functional reproducibility, we provide two complementary paths. First, we have rigorously translated the exact logic flaws from several libraries into Minimal Reproducible Examples (MREs) within our test suite, to guide practitioners on how to instantiate our framework to catch this family of issues. We distilled the structural flaws (e.g., the Diffprivlib `np.unique(y)` domain leak, the Opacus `len(data)` leak, the SmartNoise clipping omission) into self-contained test functions. Second, for `dpmm`, `mbi`, and `synthcity`, the zipped harness runs the audits against instrumented real-world library code and reports the expected detected violations.

To validate the empirical claims that these bugs existed in the real world (for the **Reproduced** badge), we rely on the public, independently verifiable PRs and issue trackers where the maintainers acknowledged and patched the flaws based on our reports. Reviewers can verify the exact commit hashes audited in **Table 2** of our paper for the code. Furthermore, we provide links to the merged GitHub PRs and Issues in our repository documentation as undeniable ground-truth evidence. Until now, here are the patched repositories:
* https://github.com/sassoftware/dpmm/issues/18
* https://github.com/ryan112358/mbi/issues/65
* https://github.com/opendp/smartnoise-sdk/issues/622
* https://github.com/opendp/smartnoise-sdk/issues/621

The diffprivlib issues were also confirmed but not yet patched.

## Notes on Reusability

The `dp-recorder` library is designed as a general framework meant to be integrated into standard CI/CD pipelines as a "privacy debugger." Developers can easily adapt it to audit their own DP libraries or algorithms by simply annotating their core noise-adding primitives with our `@audit_spec` decorator and applying `ensure_equality` hooks for invariant control flow values. The underlying PLD estimation connects seamlessly to standard `dp-accounting` routines, allowing the integration of custom mechanisms into a hybrid composition framework with minimal boilerplate code. Because the tool is agnostic to the mathematical definition of dataset adjacency, it can also easily be extended to support custom metrics.

# dp-recorder Real-World Audit Harness

Containerized entrypoint for running the packaged real-world audit examples
against instrumented library snapshots using `dp_recorder` as the auditing
backend.

The bundled submission is:

```text
tests/audit_harness/submissions/pets_submission.zip
```

It contains three examples based on libraries where we found bugs:

- `examples/dpmm_auditing/`
- `examples/mbi_auditing/`
- `examples/synthcity_auditing/`

Each example contains the instrumented library code and a neighboring `tests/`
directory with the audit implementation. The instrumentation wraps privacy
primitives with `@audit_spec` and uses equality checks for values that must
remain invariant across record/replay executions.

## Quick start

From the `dp-recorder` repository root:

```bash
python3 -m pip install rich  # optional, enables live progress output
bash tests/audit_harness/run_all.sh
```

If `rich` is not installed in the host Python environment, the harness falls
back to plain text monitoring.

This does:

1. Build `dp-recorder/tests/audit_harness/Dockerfile` (optimized layers)
2. Extract `dp-recorder/tests/audit_harness/submissions/pets_submission.zip` once to a temp directory
3. Run all manifests in **parallel** as background Docker containers
4. Collect results and print a summary report

Depending on local hardware, Docker cache state, and network speed, the full
suite usually takes 15-45 minutes. The current harness reports detected audit
violations as pytest failures, so a non-zero exit status is expected when the
known bugs are caught.

Expected summary:

```text
Manifest                        Library         Pass  XFail  XPass  Fail   Err  Status
--------------------------------------------------------------------------------------------------------------
  dpmm.json                         dpmm               7      0      0    11     0  FAIL
  mbi.json                          mbi               32      0      0     8     0  FAIL
  synthcity.json                    synthcity         10      0      0     5     0  FAIL
--------------------------------------------------------------------------------------------------------------
  TOTAL                                               49      0      0    24     0
```

The 24 failures are the expected successful interventions by the audit harness.
Full pytest logs are written to:

```text
tests/audit_harness/results/<library>.log
```

## Submission zip

The submission code lives in `dp-recorder/tests/audit_harness/submissions/pets_submission.zip` instead of as
loose files.  To re-create the zip from the `pets_submission/` source:

```bash
cd dp-recorder/pets_submission
zip -r ../tests/audit_harness/submissions/pets_submission.zip . \
  -x ".git/*" "*/.git/*" "*/__pycache__/*" ".pytest_cache/*" "*/.pytest_cache/*" "*.pyc" "poetry.lock" "figures/*"
```

## Manifest contract

Each manifest is JSON:

- `library_id` (string): logical library name
- `submission_zip` (string): path to submission zip, relative to `audit_harness/`
- `workdir` (string): working directory inside the extracted submission
- `pytest_target` (string): test file or node id (relative to `workdir`)
- `pytest_args` (list, optional): extra pytest args
- `env` (object, optional): env overrides — use `{submission}` as a placeholder
  for the extracted submission root
- `pre_cmd` (list, optional): shell commands to run before pytest

## Adding a new library

1. Add its code to `pets_submission/examples/<library>_auditing/`
2. Re-create the zip (see above)
3. Create a manifest in `manifests/` pointing at the new test path
4. Set `PYTHONPATH` using `{submission}` for submission-relative paths
5. Run: `bash dp-recorder/tests/audit_harness/run_manifest.sh <path-to-manifest>`

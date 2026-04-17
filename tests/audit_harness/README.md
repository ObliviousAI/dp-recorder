# dp-recorder Harness (Container + Manifest)

Containerized entrypoint for running audit tests against zipped submissions
using `dp_recorder` as the auditing backend.

## Quick start

From the workspace root (`oblv_repos`):

```bash
bash dp-recorder/tests/audit_harness/run_all.sh
```

This does:
1. Build `dp-recorder/tests/audit_harness/Dockerfile` (optimized layers)
2. Extract `dp-recorder/tests/audit_harness/submissions/pets_submission.zip` once to a temp directory
3. Run all manifests in **parallel** as background Docker containers
4. Collect results and print a summary report

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

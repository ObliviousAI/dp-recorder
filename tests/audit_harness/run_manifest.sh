#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

IMAGE_NAME="dp-recorder-harness:local"
MANIFEST_PATH="${1:-dp-recorder/tests/audit_harness/manifests/diffprivlib_smoke.json}"

docker build \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${IMAGE_NAME}" \
  "${SCRIPT_DIR}"

docker run --rm -t \
  -v "${WORKSPACE_ROOT}:/workspace" \
  -w /workspace \
  "${IMAGE_NAME}" \
  python -u "dp-recorder/tests/audit_harness/runner.py" --manifest "${MANIFEST_PATH}"

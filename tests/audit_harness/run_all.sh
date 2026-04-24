#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

IMAGE_NAME="dp-recorder-harness:local"
MANIFESTS_DIR="${SCRIPT_DIR}/manifests"
RESULTS_DIR="${SCRIPT_DIR}/results"

FILTER="${1:-*.json}"

if ! python3 -c "import rich" >/dev/null 2>&1; then
  echo "Error: the 'rich' Python package is required on the host to run this harness." >&2
  echo "Install the dp-recorder project first (from the repo root), e.g.:" >&2
  echo "  poetry install" >&2
  echo "or:" >&2
  echo "  pip install ." >&2
  exit 1
fi

if [ -d "${RESULTS_DIR}" ]; then
  rm -rf "${RESULTS_DIR}" || \
    docker run --rm -v "${WORKSPACE_ROOT}:/workspace" "${IMAGE_NAME}" rm -rf "dp-recorder/tests/audit_harness/results"
fi
mkdir -p "${RESULTS_DIR}"

echo "Building Docker image..."
docker build \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${IMAGE_NAME}" \
  "${SCRIPT_DIR}"

MANIFESTS=( "${MANIFESTS_DIR}"/${FILTER} )
TOTAL=${#MANIFESTS[@]}
IDX=0
PASS=0
FAIL=0

echo "Extracting submission once..."
SUBMISSION_ZIP="${SCRIPT_DIR}/submissions/pets_submission.zip"
TMP_SUBMISSION=$(mktemp -d -t audit_all_XXXXXX)
unzip -q "${SUBMISSION_ZIP}" -d "${TMP_SUBMISSION}"

if [ -d "${TMP_SUBMISSION}/pets_submission" ]; then
    echo "Detected nested pets_submission folder, unwrapping..."
    (shopt -s dotglob; mv "${TMP_SUBMISSION}/pets_submission/"* "${TMP_SUBMISSION}/")
    rmdir "${TMP_SUBMISSION}/pets_submission"
fi

mv "${TMP_SUBMISSION}" "${SCRIPT_DIR}/"
SUBMISSION_DIR_NAME=$(basename "${TMP_SUBMISSION}")
SUBMISSION_IN_CONTAINER="/workspace/dp-recorder/tests/audit_harness/${SUBMISSION_DIR_NAME}"

NAMES=()
for manifest in "${MANIFESTS[@]}"; do
  name="$(basename "${manifest}")"
  NAMES+=("${name}")
  rel="dp-recorder/tests/audit_harness/manifests/${name}"
  IDX=$((IDX + 1))

  docker run --rm -t \
    -v "${WORKSPACE_ROOT}:/workspace" \
    -w /workspace \
    "${IMAGE_NAME}" \
    python -u "dp-recorder/tests/audit_harness/runner.py" \
      --manifest "${rel}" \
      --submission-root "${SUBMISSION_IN_CONTAINER}" > "${RESULTS_DIR}/${name}.stdout" 2>&1 &

  PIDS+=($!)
done

python3 "${SCRIPT_DIR}/monitor.py" "${NAMES[@]}"

for pid in "${PIDS[@]}"; do
  wait "$pid" || FAIL=$((FAIL + 1))
done

echo "Cleaning up temporary files..."
docker run --rm -v "${WORKSPACE_ROOT}:/workspace" "${IMAGE_NAME}" rm -rf "${SUBMISSION_IN_CONTAINER}" || true
docker run --rm -v "${WORKSPACE_ROOT}:/workspace" "${IMAGE_NAME}" chmod -R 777 "dp-recorder/tests/audit_harness/results" || true

rm -rf "${SCRIPT_DIR}/${SUBMISSION_DIR_NAME}" || true

PASS=$((TOTAL - FAIL))

echo ""
python3 "${SCRIPT_DIR}/report.py"

#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
stage_name=Setup
trap 'status=$?; echo "Verification stage $stage_name failed (exit $status)." >&2' ERR
stage() { stage_name="$1"; echo "==> $stage_name"; }
results_dir="${VERIFY_RESULTS_DIR:-$PWD/artifacts/verification}"
mkdir -p "$results_dir"
rm -f "$results_dir/summary.md"
stage Source
bash scripts/ci.sh source
stage Build
bash scripts/ci.sh build
stage Assembly
bash scripts/ci.sh test assembly
stage Hosting
bash scripts/ci.sh test hosting
stage Documentation
bash scripts/ci.sh test documentation
stage "Dependency audit"
bash scripts/ci.sh audit
stage Image
bash scripts/ci.sh image
stage "Production HTTP"
bash scripts/ci.sh smoke ecommerce-store-livedocs:ci
echo 'Local verification passed. CI additionally requires secret, PR dependency and image scans.'

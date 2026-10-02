#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
python3 scripts/assemble.py
for script in scripts/*.sh; do bash -n "$script"; done
docker compose config --quiet
docker build --build-arg VCS_REF=local --build-arg BUILD_DATE=local --tag ecommerce-store-livedocs:verify .
bash scripts/smoke-container.sh ecommerce-store-livedocs:verify local
fixture_directory="$(mktemp -d build-input/verify-XXXXXX)"
trap 'rm -rf "$fixture_directory"' EXIT
python3 tests/bundle_fixtures.py "$fixture_directory"
docker build --build-arg VCS_REF=local --build-arg MANIFEST_DIRECTORY="$fixture_directory/manifests" \
  --build-arg ARTIFACT_DIRECTORY="$fixture_directory/cache" --tag ecommerce-store-livedocs:fixtures .
bash scripts/smoke-container.sh ecommerce-store-livedocs:fixtures local

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest discover -s tests -v
for script in scripts/*.sh; do bash -n "$script"; done
docker compose config --quiet
docker build --build-arg VCS_REF=local --build-arg BUILD_DATE=local --tag ecommerce-store-livedocs:verify .
bash scripts/smoke-container.sh ecommerce-store-livedocs:verify local

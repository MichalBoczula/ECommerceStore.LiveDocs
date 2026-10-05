#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command="${1:?Usage: scripts/ci.sh source|build|audit|test SUITE|image|smoke IMAGE [SHA]|publish}"
shift
results_dir="${VERIFY_RESULTS_DIR:-$PWD/artifacts/verification}"
expected_sha="${VCS_REF:-local}"

case "$command" in
  source)
    previous_args=()
    base_sha="${BASE_SHA:-}"
    if [[ -z "$base_sha" ]]; then base_sha="$(git rev-parse HEAD^ 2>/dev/null || true)"; fi
    if [[ "$base_sha" =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "$base_sha:manifests/portal.json" 2>/dev/null; then
      mkdir -p "$results_dir"
      git show "$base_sha:manifests/portal.json" > "$results_dir/previous-portal.json"
      previous_args=(--previous "$results_dir/previous-portal.json")
    fi
    python3 scripts/assemble.py "${previous_args[@]}"
    ;;
  build)
    python3 -m compileall -q scripts tests
    for script in scripts/*.sh; do bash -n "$script"; done
    docker compose config --quiet
    ;;
  audit)
    mkdir -p "$results_dir"
    python3 -m pip_audit -r requirements-ci.txt --format json --output "$results_dir/dependency-audit.json"
    ;;
  test)
    suite="${1:?Provide assembly, hosting or documentation}"
    case "$suite" in
      assembly|hosting)
        python3 scripts/run-tests.py "$suite" --results "$results_dir" \
          --summary "${VERIFY_SUMMARY_FILE:-$results_dir/summary.md}"
        ;;
      documentation)
        # Fixtures are separate from production manifests and never published.
        fixture_directory="$(mktemp -d build-input/verify-XXXXXX)"
        container=""
        cleanup() {
          if [[ -n "$container" ]]; then docker rm "$container" >/dev/null || true; fi
          rm -rf "$fixture_directory"
        }
        trap cleanup EXIT
        mkdir -p "$results_dir/documentation"
        python3 tests/bundle_fixtures.py "$fixture_directory"
        docker build --build-arg VCS_REF="$expected_sha" --build-arg BUILD_DATE="${BUILD_DATE:-local}" \
          --build-arg MANIFEST_DIRECTORY="$fixture_directory/manifests" \
          --build-arg ARTIFACT_DIRECTORY="$fixture_directory/cache" --tag ecommerce-store-livedocs:fixtures .
        container="$(docker create ecommerce-store-livedocs:fixtures)"
        site_directory="$(mktemp -d "$results_dir/documentation/site-XXXXXX")"
        docker cp "$container:/usr/share/nginx/html/." "$site_directory"
        python3 scripts/check-fixture-site.py "$site_directory"
        bash scripts/smoke-container.sh ecommerce-store-livedocs:fixtures "$expected_sha"
        echo 'Allure generation, version isolation and fixture HTTP checks passed.' | tee "$results_dir/documentation/result.txt"
        echo '### Documentation: passed' >> "${VERIFY_SUMMARY_FILE:-$results_dir/summary.md}"
        ;;
      *) echo "Unknown test suite: $suite" >&2; exit 2 ;;
    esac
    ;;
  image)
    docker build --build-arg VCS_REF="$expected_sha" --build-arg BUILD_DATE="${BUILD_DATE:-local}" \
      --tag ecommerce-store-livedocs:ci .
    ;;
  smoke)
    bash scripts/smoke-container.sh "${1:?Provide an image}" "${2:-$expected_sha}"
    ;;
  publish)
    # CI login is owned by the workflow; this command cannot publish PR/feature images.
    [[ "${GITHUB_REF:-}" == refs/heads/main ]]
    [[ "${GITHUB_EVENT_NAME:-}" == push || "${GITHUB_EVENT_NAME:-}" == workflow_dispatch ]]
    [[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
    repository=mb0101/ecommerce-store-livedocs
    scanned_id="$(docker image inspect --format '{{.Id}}' ecommerce-store-livedocs:ci)"
    for tag in "$GITHUB_SHA" latest; do
      docker tag ecommerce-store-livedocs:ci "$repository:$tag"
      test "$scanned_id" = "$(docker image inspect --format '{{.Id}}' "$repository:$tag")"
      docker push "$repository:$tag" | tee "${RUNNER_TEMP:?}/push-$tag.log"
    done
    digest="$(awk '/digest: sha256:/ {print $3}' "$RUNNER_TEMP/push-$GITHUB_SHA.log" | tail -n 1)"
    latest_digest="$(awk '/digest: sha256:/ {print $3}' "$RUNNER_TEMP/push-latest.log" | tail -n 1)"
    [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]
    test "$digest" = "$latest_digest"
    export PUBLISHED_IMAGE="$repository@$digest"
    python3 scripts/write-image-metadata.py "$results_dir/image.json"
    echo "image=$PUBLISHED_IMAGE" >> "${GITHUB_OUTPUT:?}"
    echo "Published tested image: \`$PUBLISHED_IMAGE\` (local ID \`$scanned_id\`)" >> "${GITHUB_STEP_SUMMARY:?}"
    ;;
  *) echo "Unknown verification command: $command" >&2; exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image="${1:?Usage: deploy-azure.sh IMAGE_DIGEST EXPECTED_COMMIT_SHA}"
expected_sha="${2:?Pass the full commit SHA baked into the image}"
: "${AZURE_RESOURCE_GROUP:?Configure AZURE_RESOURCE_GROUP}"
: "${AZURE_CONTAINER_APPS_ENVIRONMENT:?Configure AZURE_CONTAINER_APPS_ENVIRONMENT}"
: "${AZURE_CONTAINER_APP_NAME:?Configure AZURE_CONTAINER_APP_NAME}"
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected a full Git commit SHA' >&2; exit 1; }
[[ "$image" =~ ^(docker\.io/)?mb0101/ecommerce-store-livedocs@sha256:[0-9a-f]{64}$ ]] || {
  echo 'Expected an immutable LiveDocs image digest' >&2; exit 1;
}
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

# A failed Azure lookup is a real failure; never treat it as an absent app.
az containerapp env show --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APPS_ENVIRONMENT" --output json > "$temp_dir/environment.json"
environment_id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$temp_dir/environment.json")"
location="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["location"])' "$temp_dir/environment.json")"
az containerapp show --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APP_NAME" --output json > "$temp_dir/app.json"
python3 scripts/check-aca.py "$temp_dir/app.json" "$environment_id" >/dev/null
revision="ld-${expected_sha:0:8}-${GITHUB_RUN_ID:-$(date -u +%s)}-${GITHUB_RUN_ATTEMPT:-1}"
# Terraform owns creation, deletion, ingress, scaling and probes. CI changes only image/revision.
az containerapp update --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APP_NAME" --image "$image" --revision-suffix "$revision" --output none
az containerapp show --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APP_NAME" --output json > "$temp_dir/deployed-app.json"
fqdn="$(python3 scripts/check-aca.py "$temp_dir/deployed-app.json" "$environment_id" --expected-image "$image")"
test -n "$fqdn"
python3 scripts/smoke.py "https://$fqdn" --expected-sha "$expected_sha" --attempts 60
echo "Deployed $image to https://$fqdn/livedoc/"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf 'Deployed `%s`\n\nPortal: https://%s/livedoc/\n\nCommit: `%s`\n' \
    "$image" "$fqdn" "$expected_sha" >> "$GITHUB_STEP_SUMMARY"
fi

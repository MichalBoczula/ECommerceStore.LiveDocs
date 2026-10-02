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
az containerapp list --resource-group "$AZURE_RESOURCE_GROUP" --output json > "$temp_dir/apps.json"
action="$(python3 - "$temp_dir/apps.json" "$AZURE_CONTAINER_APP_NAME" "$environment_id" <<'PY'
import json, sys
apps = json.load(open(sys.argv[1]))
app = next((item for item in apps if item['name'] == sys.argv[2]), None)
if app:
    props = app['properties']
    actual = props.get('environmentId') or props.get('managedEnvironmentId')
    if not actual or actual.lower() != sys.argv[3].lower():
        raise SystemExit('Existing app belongs to a different ACA environment')
print('update' if app else 'create')
PY
)"
revision="ld-${expected_sha:0:8}-${GITHUB_RUN_ID:-$(date -u +%s)}-${GITHUB_RUN_ATTEMPT:-1}"
python3 scripts/render-aca.py --image "$image" --environment-id "$environment_id" \
  --location "$location" --revision "$revision" > "$temp_dir/app.yaml"
az containerapp "$action" --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APP_NAME" --yaml "$temp_dir/app.yaml" --output none
fqdn="$(az containerapp show --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_APP_NAME" --query properties.configuration.ingress.fqdn --output tsv)"
test -n "$fqdn"
python3 scripts/smoke.py "https://$fqdn" --expected-sha "$expected_sha" --attempts 60
echo "Deployed $image to https://$fqdn/livedoc/"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf 'Deployed `%s`\n\nPortal: https://%s/livedoc/\n\nCommit: `%s`\n' \
    "$image" "$fqdn" "$expected_sha" >> "$GITHUB_STEP_SUMMARY"
fi

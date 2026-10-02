#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
command -v terraform >/dev/null
command -v gh >/dev/null
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT
terraform -chdir=infra/foundation output -json github_variables > "$temp_dir/variables.json"
python3 - "$temp_dir/variables.json" "$temp_dir/variables.tsv" <<'PY'
import json,sys
sys.path.insert(0,'scripts')
from azure_config import configuration
values=json.load(open(sys.argv[1]))
required={'AZURE_CLIENT_ID','AZURE_TENANT_ID','AZURE_SUBSCRIPTION_ID','AZURE_RESOURCE_GROUP','AZURE_CONTAINER_APPS_ENVIRONMENT',
          'AZURE_CONTAINER_APP_NAME','AZURE_ARCHIVE_STORAGE_ACCOUNT','AZURE_ARCHIVE_CONTAINER','AZURE_APP_DEPLOYMENT_READY','AZURE_DEPLOY_ENABLED'}
assert set(values)==required and values['AZURE_DEPLOY_ENABLED']=='false'
configuration('archive',values)
if values['AZURE_APP_DEPLOYMENT_READY']=='true': configuration('deploy',values)
assert values['AZURE_APP_DEPLOYMENT_READY'] in {'true','false'}
with open(sys.argv[2],'w') as output:
    for name,value in values.items():
        assert isinstance(value,str) and not any(c in value for c in '\r\n\t')
        output.write(name+'\t'+value+'\n')
PY
while IFS=$'\t' read -r name value; do
  gh variable set "$name" --repo MichalBoczula/ECommerceStore.LiveDocs --body "$value"
done < "$temp_dir/variables.tsv"
echo 'Azure variables configured; automatic deployment remains disabled. Run Verify Azure readiness after app permissions are enabled.'

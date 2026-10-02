#!/usr/bin/env bash
# Reuse D/2's external backend account; only the new state container is bootstrapped outside Terraform.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
command -v az >/dev/null
command -v terraform >/dev/null
export AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id --output tsv)}"
export AZURE_TENANT_ID="${AZURE_TENANT_ID:-$(az account show --query tenantId --output tsv)}"
export LD_STATE_RESOURCE_GROUP="${LD_STATE_RESOURCE_GROUP:-rg-ecommerce-terraform-state}"
export LD_STATE_STORAGE_ACCOUNT="${LD_STATE_STORAGE_ACCOUNT:-$(python3 -c 'import hashlib,os; print("stecomtf" + hashlib.sha256(os.environ["AZURE_SUBSCRIPTION_ID"].encode()).hexdigest()[:14])')}"
export LD_LOCATION="${LD_LOCATION:-northeurope}"
python3 - <<'PY'
import json,os,re,sys
from pathlib import Path
sys.path.insert(0,'scripts')
from azure_config import GUID
for name in ['AZURE_SUBSCRIPTION_ID','AZURE_TENANT_ID']:
    assert re.fullmatch(GUID,os.environ[name]), f'Invalid {name}'
assert re.fullmatch(r'[a-z0-9]{3,24}',os.environ['LD_STATE_STORAGE_ACCOUNT'])
assert re.fullmatch(r'[a-zA-Z0-9_.()-]{1,90}',os.environ['LD_STATE_RESOURCE_GROUP'])
assert os.environ['LD_STATE_RESOURCE_GROUP'].lower() not in ['rg-ecommerce-dev','rg-ecommerce-bootstrap','rg-ecommerce-livedocs-archive']
values={'subscription_id':os.environ['AZURE_SUBSCRIPTION_ID'],'tenant_id':os.environ['AZURE_TENANT_ID'],'location':os.environ['LD_LOCATION']}
path=Path('infra/foundation/setup.auto.tfvars.json')
if path.exists():
    old=json.loads(path.read_text())
    assert all(old.get(k)==v for k,v in values.items()), 'Existing foundation settings disagree; review them before any mutation'
backend={'resource_group_name':os.environ['LD_STATE_RESOURCE_GROUP'],'storage_account_name':os.environ['LD_STATE_STORAGE_ACCOUNT'],
         'container_name':'livedocs-foundation-state','key':'ecommerce/livedocs-foundation.tfstate'}
content=''.join(f'{k} = {json.dumps(v)}\n' for k,v in backend.items())
path=Path('infra/foundation/backend.hcl')
assert not path.exists() or path.read_text()==content, 'Existing backend disagrees; do not migrate or start a new state accidentally'
PY
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
for group in rg-ecommerce-bootstrap rg-ecommerce-dev; do
  if ! az group show --name "$group" --output none; then
    echo 'Run the ECommerceStore.TerraformState D/2 bootstrap first; its retained groups are required.' >&2
    exit 1
  fi
done
temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT
az storage account show --resource-group "$LD_STATE_RESOURCE_GROUP" \
  --name "$LD_STATE_STORAGE_ACCOUNT" --output json > "$temp_dir/account.json"
python3 - "$temp_dir/account.json" <<'PY'
import json,sys
account=json.load(open(sys.argv[1]))
assert account.get('allowSharedKeyAccess') is False and account.get('allowBlobPublicAccess') is False, 'Use the private Entra-authenticated external state account from D/2'
PY
az storage container create --account-name "$LD_STATE_STORAGE_ACCOUNT" \
  --name livedocs-foundation-state --auth-mode login --public-access off --output none
python3 - <<'PY'
import json,os
from pathlib import Path
values={'subscription_id':os.environ['AZURE_SUBSCRIPTION_ID'],'tenant_id':os.environ['AZURE_TENANT_ID'],'location':os.environ['LD_LOCATION']}
path=Path('infra/foundation/setup.auto.tfvars.json')
if not path.exists(): path.write_text(json.dumps(values,indent=2)+'\n')
backend={'resource_group_name':os.environ['LD_STATE_RESOURCE_GROUP'],'storage_account_name':os.environ['LD_STATE_STORAGE_ACCOUNT'],
         'container_name':'livedocs-foundation-state','key':'ecommerce/livedocs-foundation.tfstate'}
Path('infra/foundation/backend.hcl').write_text(''.join(f'{k} = {json.dumps(v)}\n' for k,v in backend.items()))
PY
terraform -chdir=infra/foundation init -input=false -lockfile=readonly -backend-config=backend.hcl
echo 'Foundation backend initialized. Review a saved Terraform plan, then apply it locally.'

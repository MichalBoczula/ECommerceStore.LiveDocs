# Azure setup and rollout — LD/3

## Current status and ownership

The Azure setup has not been executed. Subscription/tenant identifiers alone do
not create an identity, environment or app. The first rollout needs the D/2
foundation and an Infrastructure-managed ACA environment/app.

| Resource | Owner/state | Survives application Destroy |
| --- | --- | --- |
| External Terraform account and state containers | One-time D/2 setup outside Terraform | Yes |
| Retained `rg-ecommerce-bootstrap` and `rg-ecommerce-dev` | TerraformState bootstrap state | Yes |
| Report account/container, archive group, LiveDocs identity/federation | LiveDocs `infra/foundation`, separate persistent state | Yes |
| Shared ACA environment | Infrastructure application state | No |
| LiveDocs app lifecycle, ingress, probes and scaling | `infra/app` module called by Infrastructure application state | No |
| App image and revision suffix | LiveDocs delivery workflow | Recreated from an immutable image after teardown |

LiveDocs does not create the shared environment or retained application group.
Infrastructure must include the app in its state, so its Destroy cannot leave an
untracked LiveDocs app behind. CI refuses to create an absent app or reconcile
Terraform host settings. It changes only image and revision suffix.

## 1. Complete D/2 on your machine

Use WSL/Bash, Azure CLI, GitHub CLI and Terraform **1.16.5**. Log in locally and
select the intended subscription. Follow
[TerraformState first setup](https://github.com/MichalBoczula/ECommerceStore.TerraformState#first-setup-on-your-machine),
including saved-plan apply and GitHub configuration. Run **Verify development backend**
in Infrastructure before provisioning applications.

This creates the independent state account and retained groups. Its current
Infrastructure root is backend-only: an ACA environment must still be implemented
and applied there. Do not create the shared environment through an untracked CLI
command as a shortcut.

## 2. Create the persistent LiveDocs archive and identity

From this repository after LD/3 is merged:

```bash
az login
az account set --subscription YOUR_SUBSCRIPTION_ID
gh auth login

# Optional when D/2 used custom names:
# export LD_STATE_RESOURCE_GROUP=YOUR_EXTERNAL_STATE_GROUP
# export LD_STATE_STORAGE_ACCOUNT=YOUR_EXTERNAL_STATE_ACCOUNT
bash scripts/init-foundation.sh
terraform -chdir=infra/foundation plan -out=livedocs-foundation.tfplan
terraform -chdir=infra/foundation apply livedocs-foundation.tfplan
bash scripts/configure-github-azure.sh
```

The initialization helper checks the existing D/2 groups and private external
account. It creates only `livedocs-foundation-state` in that external account,
then initializes the fixed key `ecommerce/livedocs-foundation.tfstate`. It never
creates/imports the backend account and never selects development/bootstrap state.
Existing conflicting backend/configuration files fail before Azure mutation.

The helper derives subscription and tenant IDs from the selected local Azure
session, unless `AZURE_SUBSCRIPTION_ID` and `AZURE_TENANT_ID` are explicitly supplied.
It writes ignored `infra/foundation/setup.auto.tfvars.json` and `backend.hcl`.
Provider versions/locks match the current D/2 foundation: AzureRM **5.8.0**.

The operator needs management/access-assignment rights for these scoped resources,
as in the D/2 bootstrap. The external account's operator Blob access from D/2
allows creation and use of the separate LiveDocs state container. Provider
registration remains owned by the infrastructure setup; Microsoft.Storage and
Microsoft.ManagedIdentity must be registered.

The saved plan creates:

- `rg-ecommerce-livedocs-archive` with a `CanNotDelete` lock;
- a deterministic, globally unique Standard LRS report account and private `livedocs` container;
- HTTPS/TLS 1.2, Shared Key/public blobs disabled, versioning and 30-day blob/container soft delete;
- `id-ecommerce-livedocs-dev` in the retained bootstrap group;
- federation restricted to this repo's `main` branch;
- read-only archive access for CI and container-scoped Blob Contributor for the local bootstrap operator.

Account public network access allows authenticated GitHub-hosted runners; blobs
remain private. The account/group lock protects management-plane deletion, not
blob deletion. Keep referenced bundles indefinitely; soft delete/versioning help
recovery but are not a tested backup/restore procedure. No expiry rule is installed.

`enable_app_deployment` initially defaults to false. The archive and identity can
be created before ACA exists. No app/environment permissions are assigned yet,
and automatic deployment remains disabled.

## 3. Provision the environment and app through Infrastructure

When Infrastructure adds its ACA environment, include this module in that same
application state. Pin `source` to the merged LD/3 commit, replacing the placeholder:

```hcl
module "livedocs" {
  source              = "git::https://github.com/MichalBoczula/ECommerceStore.LiveDocs.git//infra/app?ref=LD3_COMMIT_SHA"
  resource_group_name = data.azurerm_resource_group.development.name
  environment_id      = azurerm_container_app_environment.development.id
  initial_image       = var.livedocs_initial_image
}
```

The caller's resource names are illustrative; use the actual Infrastructure
resources. `livedocs_initial_image` must be a published
`mb0101/ecommerce-store-livedocs@sha256:<64-character-digest>` from a successful
LiveDocs CI summary. The Docker Hub repository must be public. No registry secret
or runtime storage mount is needed.

The module creates the dedicated app with public HTTPS, port 8080, three HTTP
probes, single revision mode, five inactive revisions, 0.25 vCPU / 0.5 GiB and HTTP
scaling from 0 to 1 replica. Terraform ignores only image/revision changes made
by delivery CI; it owns all other host configuration and deletion. Recreating the
app uses the supplied initial digest, so maintain a known-good digest for reapply.

## 4. Enable app-scoped permissions

After Infrastructure applies the environment/app, add these values to the ignored
`infra/foundation/setup.auto.tfvars.json`, preserving subscription/tenant settings:

```json
{
  "enable_app_deployment": true,
  "container_apps_environment_name": "cae-ecommerce-dev",
  "container_app_name": "ca-ecommerce-livedocs-dev"
}
```

Use the actual environment/app names if different. Then save and apply a new
foundation plan and rerun `bash scripts/configure-github-azure.sh`.

The new assignments grant app read/write only on the dedicated app and environment
read/join only on its selected environment. There is no subscription/RG-wide
deployment grant, app/environment deletion grant, role-assignment grant or archive
write grant for CI. The identity is not assigned to the running container.

Federation values:

| Field | Value |
| --- | --- |
| Issuer | `https://token.actions.githubusercontent.com` |
| Subject | `repo:MichalBoczula/ECommerceStore.LiveDocs:ref:refs/heads/main` |
| Audience | `api://AzureADTokenExchange` |

The identity's client ID is an application/client ID, not a principal/object ID.
The helper writes these repository **variables** with local GitHub CLI access:

| Variable | Purpose |
| --- | --- |
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | OIDC identity and subscription |
| `AZURE_RESOURCE_GROUP` | Retained application group |
| `AZURE_CONTAINER_APPS_ENVIRONMENT`, `AZURE_CONTAINER_APP_NAME` | Existing target resources |
| `AZURE_ARCHIVE_STORAGE_ACCOUNT`, `AZURE_ARCHIVE_CONTAINER` | Private archive boundary |
| `AZURE_APP_DEPLOYMENT_READY` | True only after the app-scoped assignments are enabled |
| `AZURE_DEPLOY_ENABLED` | Always set false by setup; opt into automatic delivery later |

No client secret, storage key or `AZURE_CREDENTIALS` JSON is needed.

## 5. Verify and deliver

Run **Verify Azure readiness** on `main`. It validates configuration before login,
uses OIDC to read the private container and selected bundles, inspects the Terraform
host configuration, and smoke-tests the public endpoint without mutation. Initial
empty manifests verify container access; the first real bundle download occurs
after LD/4 publishes references. RBAC propagation can delay access; inspect and
rerun a failed verification once the grant is effective.

Then run **LiveDocs CI and delivery** on `main` with `deploy=true`. CI builds,
smoke-tests and scans the image before publishing that exact image and updating the
existing app by digest. Deployment checks app configuration before mutation and
checks the image plus public commit identity afterwards.

Private production packages are prefetched only on trusted main push/manual runs,
using read-only OIDC access, into the build context before Docker starts. References
must match the configured account/container and project/commit/checksum path.
Credentials are never passed into Docker. PR/feature runs with nonempty manifests
validate references and build isolated fixtures; they do not authenticate to Azure
or validate private package bytes. Main publication validates all selected packages.

The workflow summary records the image digest, source commit and portal URL.
Enable `AZURE_DEPLOY_ENABLED=true` only if automatic main delivery is desired.
Host readiness does not imply a passing BDD suite or healthy service APIs.

## Rollback and teardown

Keep the previous successful digest and source commit from CI. To roll back using
an authenticated local session, export the three resource variables and run:

```bash
bash scripts/deploy-azure.sh \
  'mb0101/ecommerce-store-livedocs@sha256:PREVIOUS_DIGEST' \
  'PREVIOUS_FULL_SOURCE_COMMIT'
```

This creates a fresh revision from the prior immutable image and checks the prior
commit. Keep the corresponding Docker Hub images. Never roll back using `latest`.
Single revision mode keeps the previous revision until the next becomes ready;
a failed public check does not automatically reverse an already-ready revision.

Before application Destroy, set `AZURE_DEPLOY_ENABLED=false`, set the persistent
foundation's `enable_app_deployment=false`, save/apply its plan and rerun the GitHub
configuration helper. This removes app/environment-scoped assignments while the
resources still exist and marks deployment unready. Then run Infrastructure Destroy.
The separate foundation state, report archive, identity and external state store
remain. Reapply Infrastructure, reenable app-scoped assignments and verify readiness
before delivering again. Missing resources fail deployment; CI never recreates a
destroyed environment.

Terraform foundation resources use `prevent_destroy`; there is no foundation
Destroy workflow. Keep plans/state private and use current remote state for updates.
Back up/recover foundation state through the external account's established strategy;
this setup does not change the shared Terraform account's retention settings.

## Verification limits

PR CI validates Terraform schemas and mocked plans, Python regressions, real Docker
generation/HTTP behavior and image scanning. These checks do not prove Azure OIDC,
RBAC propagation, public ingress, archive recovery or apply/destroy/reapply. Those
require the explicitly run Azure setup/readiness/rollout with your subscription.

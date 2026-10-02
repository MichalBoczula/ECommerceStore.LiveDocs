# Azure setup and rollout

## Existing infrastructure

Create the resource group and Azure Container Apps environment using the
portfolio infrastructure first. This repository does not create an environment,
storage account, registry or resource group. Its deployment script manages a
dedicated LiveDocs container app in the existing environment.

The Docker Hub repository `mb0101/ecommerce-store-livedocs` must be public.
There are no registry credentials in the ACA app and no runtime storage mount.

## GitHub OIDC

Use an Entra service principal or user-assigned managed identity with a federated
credential for this repository's `main` branch:

| Field | Value |
| --- | --- |
| Issuer | `https://token.actions.githubusercontent.com` |
| Subject | `repo:MichalBoczula/ECommerceStore.LiveDocs:ref:refs/heads/main` |
| Audience | `api://AzureADTokenExchange` |

The workflow grants `id-token: write` only to its Azure job. No client secret or
`AZURE_CREDENTIALS` JSON is required. The client ID is the application's/identity's
client ID, not its principal/object ID.

For initial app creation, give the identity **Container Apps Contributor** on the
target resource group. This built-in role includes managed-environment read/join
permissions as well as container-app management. After bootstrapping, a custom role
can narrow app writes to the dedicated app while retaining resource-group app-list
access, environment read access and any required environment join permission.
This workflow never creates role assignments or changes identities. See
[the role definition](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers#container-apps-contributor).

## Repository variables

Configure these as GitHub Actions **variables**, not Docker Hub secrets:

| Variable | Value |
| --- | --- |
| `AZURE_CLIENT_ID` | OIDC identity client ID |
| `AZURE_TENANT_ID` | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Target subscription ID |
| `AZURE_RESOURCE_GROUP` | Existing portfolio resource group |
| `AZURE_CONTAINER_APPS_ENVIRONMENT` | Existing ACA environment name in that resource group |
| `AZURE_CONTAINER_APP_NAME` | Dedicated LiveDocs app name |
| `AZURE_DEPLOY_ENABLED` | `true` enables deployment after successful main publication; otherwise disabled |

No resource names or subscription IDs are assumed. To perform the first delivery,
dispatch **LiveDocs CI and delivery** on `main` with `deploy=true`. This explicitly
requests Azure delivery even while automatic deployment is disabled.

## Local deployment

With Azure CLI installed and authenticated, set the three resource variables above,
then use the immutable image reference from the publishing workflow summary:

```bash
az login
az account set --subscription '<subscription-id>'
export AZURE_RESOURCE_GROUP='<existing-resource-group>'
export AZURE_CONTAINER_APPS_ENVIRONMENT='<existing-environment-name>'
export AZURE_CONTAINER_APP_NAME='<dedicated-livedocs-app-name>'
bash scripts/deploy-azure.sh \
  'mb0101/ecommerce-store-livedocs@sha256:<64-character-digest>' \
  '<full-40-character-source-commit-sha>'
```

The script validates the image and identity before mutation. It reads the existing
environment, creates the app if absent or updates it if present, and refuses to
move an existing app to a different environment. An Azure lookup error fails the
deployment rather than being treated as a missing resource.

## Configuration and health

The generated app specification sets:

- external HTTP ingress on port 8080, with HTTPS required;
- a single active revision and up to five retained inactive revisions;
- startup/readiness checks on `/health/ready`, liveness on `/health/live`;
- 0.25 vCPU / 0.5 GiB, min replicas 0, max replicas 1;
- an HTTP scaling rule, with a concurrent request threshold of 10.

The app is dedicated to LiveDocs; deployment reconciles this host configuration.
After Azure provisioning, a public smoke check verifies the expected commit SHA.
Scale-to-zero can introduce a cold start. Cost depends on traffic and shared
environment configuration; zero replicas does not imply zero total Azure cost.

## Rollback

Keep the previous successful **image digest and source commit** from the workflow
summary. To roll back, run the deployment script with that pair. It creates a fresh
revision from the older immutable snapshot and verifies the older source commit.
Keep those Docker Hub images; deleting an image can prevent rollback or a new pull.

Single-revision mode keeps the old revision serving until the new revision becomes
ready. A failed public smoke check fails the workflow; it does not automatically
roll back an already-ready revision. Use the last known-good digest if a rollback
is needed. Never deploy the mutable `latest` tag as a rollback target.

## Shared Terraform boundary

The shared environment/resource group can remain in Terraform. Do not have two
systems independently own the dedicated app's template. If Terraform later owns
this app, coordinate the image/revision configuration before importing it and
adjust the pipeline's ownership explicitly.

## References

- [Azure Container Apps template specification](https://learn.microsoft.com/en-us/azure/container-apps/azure-resource-manager-api-spec)
- [Azure health probes](https://learn.microsoft.com/en-us/azure/container-apps/health-probes)
- [Azure Login OIDC](https://github.com/Azure/login#login-with-openid-connect-oidc)

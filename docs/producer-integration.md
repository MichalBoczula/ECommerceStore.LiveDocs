# LD/5: Products to Blob to LiveDocs

## Delivery flow

Products' CI exports OpenAPI, business flows, validation policies and operation
links from the same source checkout as its acceptance tests. It uploads raw
Allure results, then calls a commit-pinned LiveDocs reusable packaging workflow.
The resulting ZIP must validate before Products' quality gate permits its image
build, scan and publication. Only a successful master image job permits the
optional archive job. PRs package real inputs but never upload to Azure.

The archive writer uploads `reports/products/<commit>/<sha256>.zip` and then a
small discovery receipt at `candidates/v1/products/<run-id>-<sha256>.json` in the
private **livedocs** container. Both uploads refuse overwrite; retries accept
existing objects only after byte-for-byte verification. The receipt contains the
manifest reference, not credentials. Multiple different bundles for one run are
ambiguous and require operator resolution before import.

LiveDocs' import workflow runs manually or every 30 minutes when explicitly
enabled. It reads receipts, chooses a newer successful Products master push in
`.github/workflows/dotnet.yml`, verifies its source SHA and run identity, downloads
the package and validates checksums, inventory and source identity. It changes
only the selected development manifest and opens a PR in this repository.
Products has no GitHub write access to LiveDocs. In-progress/failed source runs
are never imported. Imports cannot modify released versions or automatically
create a new version.

The PR token comes from a GitHub App installed only in LiveDocs. Normal PR checks
therefore run; the default GITHUB_TOKEN would suppress workflow-triggering PR
events. GitHub owns reviews/merge, not the importer. Repeated discovery preserves
an existing candidate branch/PR without force-pushing or reopening a closed PR.

Image CI fetches every retained package using a reader identity **outside Docker**,
validates the cache and transfers the verified inputs to the production image job.
Any unavailable or corrupt package blocks publication. Neither Java/Allure nor
Azure identity is present in the static Nginx runtime. Application Terraform
selects and deploys the new image digest together with the application.

## One-time Azure and GitHub setup

Azure resources belong to ECommerceStore.Infrastructure. Its existing persistent
`foundations/livedocs` root creates the private archive. LD/5 adds writer/reader
identities with roles scoped to the `livedocs` container. It does not give them
access to a mobile-phone photos container or application deployment roles.
The existing persistent root currently creates the account and `livedocs`
container. A mobile-phone photos container can coexist in that same account with
its own access roles. LD/5 does not create photo storage or migrate an existing
photo account; application storage configuration remains in Infrastructure.

**Configure protected GitHub environments before applying reader federation.**
In LiveDocs create:

- `livedocs-archive-build`: selected deployment branches `main` and any explicitly
  supported development branches; no PR merge refs. The import workflow runs only
  from main, even when targeting a version branch.
- `livedocs-archive-pr`: require Mike/an authorized reviewer, disable administrator
  bypass, and allow `refs/pull/*/merge`. Approve only trusted internal PRs. Keep
  self-review available if Mike opens his own PRs. This protects the Azure OIDC
  subject itself, rather than relying only on a condition in editable PR YAML.
  A PR needing private inputs must receive this archive-read approval before CI
  can complete. Fork PRs are rejected by the checked-in workflow.

A bare `pull_request` federated credential is intentionally not created: fork PRs
could otherwise request that subject in their own workflow. Build/import and PR
readers use the two protected environment subjects. Neither environment deploys
an application; its purpose is archive access protection.

After merging the Infrastructure identity PR, initialize the existing foundation,
create/review a fresh Terraform plan, apply it as the operator and read:

```powershell
terraform "-chdir=foundations/livedocs" output -raw archive_storage_account
terraform "-chdir=foundations/livedocs" output -raw products_livedocs_client_id
terraform "-chdir=foundations/livedocs" output -raw livedocs_reader_client_id
terraform "-chdir=foundations/livedocs" output -raw livedocs_tenant_id
terraform "-chdir=foundations/livedocs" output -raw livedocs_subscription_id
```

Set **repository variables**, using the same archive account in both repositories:

| Variable | ProductsCatalog | ECommerceStore.LiveDocs |
| --- | --- | --- |
| `AZURE_SUBSCRIPTION_ID` | Foundation subscription ID | Same ID |
| `AZURE_TENANT_ID` | Foundation tenant ID | Same ID |
| `LIVEDOCS_STORAGE_ACCOUNT` | Archive account | Same account |
| `LIVEDOCS_AZURE_CLIENT_ID` | Products writer client ID | LiveDocs reader client ID |
| `LIVEDOCS_VERSION` | `v1` initially | Not used |
| `LIVEDOCS_PUBLISH_ENABLED` | Set `true` after setup | Not used |
| `LIVEDOCS_IMPORT_ENABLED` | Not used | Set `true` after the first successful manual import |
| `LIVEDOCS_IMPORT_VERSION` | Not used | `v1` initially |
| `LIVEDOCS_IMPORT_BRANCH` | Not used | `main` initially |
| `LIVEDOCS_APP_ID` | Not used | GitHub App ID |

The enable flags deliberately default off until Azure setup exists. Packaging and
all existing service/image checks still run. Once publication is enabled, missing
configuration or failed uploads fail the producer run. Nonempty LiveDocs manifests
always require archive retrieval; there is no fallback to fixtures or skipped inputs.

Create a GitHub App with **Contents: read/write** and **Pull requests: read/write**,
install it only in ECommerceStore.LiveDocs, generate its private key and save it
as repository secret `LIVEDOCS_APP_PRIVATE_KEY`. No producer App token/PAT is needed.
The App has no Azure or Infrastructure access. Existing Docker Hub secrets remain
unchanged. OIDC uses IDs, not a long-lived Azure client secret or SAS.

## First publication and version branches

1. Merge LiveDocs tooling, then Products' pinned integration and Infrastructure's
   identity configuration. Products can package while archive publication is off.
2. Complete the setup above and enable Products archive publication. A new master
   push runs full tests/build/security/image checks before uploading a real bundle.
3. Wait for that producer workflow to finish successfully. In LiveDocs run
   **Import documentation** from main, with `v1` and target branch `main`.
4. Review its manifest PR and approve private archive reads in the PR environment.
   Confirm full LiveDocs CI, merge, and inspect image publication metadata.
5. Select the new digest through application Infrastructure. Enable scheduled
   imports after this first verified handoff. GitHub schedules may be delayed;
   manual import uses the same validation and is an immediate fallback.

For v2, create a LiveDocs development branch containing an explicit v2 manifest
entry, retain v1, allow that branch in `livedocs-archive-build`, then set Products'
`LIVEDOCS_VERSION=v2` and import version/target branch accordingly. PR and branch CI
validate/generate the image; only main publishes SHA/latest production tags. Freeze
released manifest entries through review. A source commit identifies the service
image and documentation bundle; their separate CI/merge operations are not an
atomic deployment transaction. Terraform coordinates the selected release images.

## Retention and boundaries

Preserve every bundle referenced by supported versions, plus any pending candidate
PR. Versioning, soft delete and the existing management lock aid recovery; they
are not a WORM policy. Blob Data Contributor can delete blobs. The publisher's
no-overwrite and content checks do not prevent administrator deletion. Do not
configure blanket expiry on referenced packages. Application teardown must retain
this foundation and its state.

Only synthetic test data should appear in acceptance attachments. Generated HTML
is baked into the image, not committed to Git or uploaded from a running replica.
Live Azure upload/import and ACA rollout require the operator setup above; mock
regressions and PR CI alone do not prove that live RBAC has propagated.

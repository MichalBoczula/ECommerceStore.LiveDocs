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
Azure identity is present in the static Nginx runtime. The LiveDocs Terraform hosting root
selects and deploys the new image digest through a reviewed manual apply.

## One-time Azure and GitHub setup

Azure resources belong to
[ECommerceStore.LiveDocs.Terraform](https://github.com/MichalBoczula/ECommerceStore.LiveDocs.Terraform).
Its persistent `archive/` root creates a dedicated private account and `livedocs`
container, Products writer and LiveDocs reader identities, and container-scoped
roles. Its separate `hosting/` root deploys the baked image to the shared ACA
environment and can be destroyed after a demo without deleting archive inputs.
Products photo storage remains independent.

The old `ECommerceStore.Infrastructure` was renamed
`-DEPRECATED-ECommerceStore.Infrastructure` and contains a legacy
`foundations/livedocs` root. If it was applied, inspect its actual state and archive
before provisioning: follow the new repository's archive adoption checklist.
Do not create two Terraform owners or repoint retained manifests to an empty account.

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

From the new Terraform repository, provision the archive root following its
README. Reader federation defaults off until the protected environments above
exist. Then enable `enable_reader_federation`, review and apply a fresh archive
plan, and read the non-secret output:

```powershell
$archiveJson = (& $ecommerceTerraform '-chdir=archive' output -json archive_configuration) -join "`n"
if ($LASTEXITCODE -ne 0) { throw 'Archive output lookup failed' }
$archive = $archiveJson | ConvertFrom-Json
$archive | Format-List
```

Set **repository variables**, using the same archive account in both repositories:

| Variable | ProductsCatalog | ECommerceStore.LiveDocs |
| --- | --- | --- |
| `AZURE_SUBSCRIPTION_ID` | `subscription_id` | Same ID |
| `AZURE_TENANT_ID` | `tenant_id` | Same ID |
| `LIVEDOCS_STORAGE_ACCOUNT` | `storage_account_name` | Same account |
| `LIVEDOCS_AZURE_CLIENT_ID` | `products_writer_client_id` | `reader_client_id` |
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

1. Merge LiveDocs tooling, then Products' pinned integration and LiveDocs Terraform's
   archive/identity configuration. Products can package while archive publication is off.
2. Complete the setup above and enable Products archive publication. A new master
   push runs full tests/build/security/image checks before uploading a real bundle.
3. Wait for that producer workflow to finish successfully. In LiveDocs run
   **Import documentation** from main, with `v1` and target branch `main`.
4. Review its manifest PR and approve private archive reads in the PR environment.
   Confirm full LiveDocs CI, merge, and inspect image publication metadata.
5. Select the new digest through the LiveDocs Terraform hosting root. Enable scheduled
   imports after this first verified handoff. GitHub schedules may be delayed;
   manual import uses the same validation and is an immediate fallback.

For v2, create a LiveDocs development branch containing an explicit v2 manifest
entry, retain v1, allow that branch in `livedocs-archive-build`, then set Products'
`LIVEDOCS_VERSION=v2` and import version/target branch accordingly. PR and branch CI
validate/generate the image; only main publishes SHA/latest production tags. Freeze
released manifest entries through review. A source commit identifies the service
image and documentation bundle; their separate CI/merge operations are not an
atomic deployment transaction. Reviewed Terraform applies coordinate the selected service and documentation images.

## Retention and boundaries

Preserve every bundle referenced by supported versions, plus any pending candidate
PR. Versioning, soft delete and Terraform archive destruction guards aid retention;
they are not a WORM policy. A legacy adopted archive may also retain its management lock. Blob Data Contributor can delete blobs. The publisher's
no-overwrite and content checks do not prevent administrator deletion. Do not
configure blanket expiry on referenced packages. Demo hosting teardown must retain
the archive root, its resources and its state.

Only synthetic test data should appear in acceptance attachments. Generated HTML
is baked into the image, not committed to Git or uploaded from a running replica.
Live Azure upload/import and ACA rollout require the operator setup above; mock
regressions and PR CI alone do not prove that live RBAC has propagated.

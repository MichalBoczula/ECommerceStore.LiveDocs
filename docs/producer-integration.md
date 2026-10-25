# LD/5: Products to Blob to LiveDocs

## Delivery flow

Products CI exports OpenAPI, business flows, validation policies, operation links,
Reqnroll features and actual Allure results from one source checkout. Its pinned
LiveDocs packaging workflow validates the source ZIP before the Products quality
gate. Successful master image publication automatically uploads the bundle;
PRs never upload to Azure. There is no publication enable variable.

The archive writer uploads `reports/products/<commit>/<sha256>.zip`, then a
receipt at `candidates/v1/products/<run-id>-<sha256>.json` in private container
`stecproductsdevmb261013/livedocs`. Retries download existing objects and compare
bytes; different content is refused. Neither URLs nor receipts contain credentials.

LiveDocs selects a receipt's `reference` object in `manifests/portal.json` through
a PR. Image CI downloads every retained archive outside Docker, verifies its
checksum, size, inventory, attachments and source identity, and transfers the
verified cache to the image job. Allure HTML is generated in the Docker builder.
The final Nginx image is smoke-tested and scanned before Docker Hub publication.
A missing or corrupt archive blocks publication; the deployed image keeps serving
its existing snapshot.

## Current Products snapshot

The development v1 manifest selects successful Products master push
[40205595842](https://github.com/MichalBoczula/ProductsCatalog/actions/runs/40205595842):

| Field | Value |
| --- | --- |
| Source commit | `48154e5566402b65cb686c4c7eda6bed1d30d707` |
| Bundle SHA-256 | `f64189b99cfe8355440b0b0c99c72576e263db3729104a40119ca9a198eeaf7d` |
| Bundle size | 216581 bytes |
| Storage account / container | `stecproductsdevmb261013` / `livedocs` |
| Project page | `/livedoc/v1/products/` |
| Allure report | `/livedoc/v1/products/allure/` |

The complete immutable Blob URL is in the manifest. Products CI verified both
bundle and receipt by downloading and comparing bytes on an archive-job retry.
The LiveDocs image build independently revalidates the selected source bundle.

## One-time setup for image builds

[ECommerceStore.Terraform](https://github.com/MichalBoczula/ECommerceStore.Terraform)
owns all current Azure resources in one root/state, including the shared storage
account, private `livedocs` container, ACA environment and LiveDocs app. No new
Azure resources are needed for this report. Do not apply the older dedicated
LiveDocs Terraform roots to these resources. Existing archives in other accounts
are not moved or deleted; see [ADR-0007](adr/0007-shared-store-products-publication.md).

In **ECommerceStore.LiveDocs**, add this **repository Actions secret**:

| Secret | Value |
| --- | --- |
| `LIVEDOCS_STORAGE_SAS_TOKEN` | Complete container SAS query string, including all fields and `sig` |

The image reader only needs **read** permission on `livedocs`, HTTPS-only. The
Products writer's existing container SAS also works for the first publication.
Do not paste the token into Git, a manifest, an image argument or an issue.
An expired token must be replaced before another image can be built.

`LIVEDOCS_STORAGE_ACCOUNT` is an optional repository variable; the default is
`stecproductsdevmb261013`. Keep the existing `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN` publication secrets. Image CI needs no Azure client/tenant/
subscription variables, OIDC federation or GitHub import App.

The workflow retains `livedocs-archive-pr` and `livedocs-archive-build` environments.
If they have protection rules, approve the trusted PR's archive-read job as required.
Fork PRs cannot read the private inputs. Only internal, reviewed workflow changes
should receive access to the archive secret. The secret is passed to the Azure CLI
prefetch step, never to the Docker build or runtime.

## Publish and deploy

1. Confirm the producer run completed successfully and select its exact receipt
   reference in an existing development version. Keep all retained references.
2. Run the LiveDocs manifest PR checks, including private prefetch, real Allure
   generation, production-container HTTP checks and image scan. Merge after they pass.
3. Let main CI publish the tested image. Read the immutable digest and commit from
   the `livedocs-image/image.json` artifact or publication summary.
4. In ECommerceStore.Terraform, replace only `app_images.livedocs` with that digest,
   retaining all other application image entries. Review and apply a fresh plan:

   ```powershell
   terraform plan "-out=livedocs.tfplan"
   terraform apply livedocs.tfplan

   $liveDocsUrl = (terraform output -json app_urls | ConvertFrom-Json).livedocs
   Invoke-RestMethod "$liveDocsUrl/health/ready" -TimeoutSec 180
   Invoke-RestMethod "$liveDocsUrl/build-info.json" -TimeoutSec 180
   Start-Process "$liveDocsUrl/livedoc/v1/products/"
   ```

Compare `build-info.json.commitSha` with the selected LiveDocs image commit.
The existing ACA changes its revision; no BFF routing or storage connection is
needed by the running container. Blob uploads alone do not change a running report.

For v2, add an explicit development v2 manifest, retain v1, and select the producer
receipt for v2. Released manifest versions cannot be changed or removed. Only main
publishes production tags. Service and documentation publication remain separate
operations; a source SHA links their inputs.

## Optional automated importer

The existing **Import documentation** workflow remains off for scheduled runs
unless `LIVEDOCS_IMPORT_ENABLED=true`. It is not needed for the first manual
manifest PR, and the SAS image-reader setup above does not configure it.

Its existing setup requires archive-reader OIDC variables
`LIVEDOCS_AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` and
`LIVEDOCS_STORAGE_ACCOUNT`, with access restricted to the protected
`livedocs-archive-build` environment. It also requires `LIVEDOCS_APP_ID` and
`LIVEDOCS_APP_PRIVATE_KEY` for an App installed only in LiveDocs with Contents and
Pull requests read/write. Default `GITHUB_TOKEN` PR writes would suppress PR CI.
Do not enable it without that separate configuration. No import identities or
resources are provisioned by this publication change.

The importer verifies successful producer master-push provenance, refuses ambiguous
receipts or rollbacks, and opens a PR without merging or deploying. Discovery is
main-owned; optional version/branch variables select an existing development target.

## Retention

Preserve every bundle referenced by a retained version and any pending candidate
PR. Do not set blanket expiration on those blobs. The current archive shares the
store's account and Terraform state: a full shared-root destroy removes it too.
Keep the account/container and backend state when cleaning up application hosting.
This change does not migrate any older archive.

Acceptance attachments must contain synthetic data. The archive is private, but
reports baked into a public image or served by public ACA are public. The runtime
contains no Blob credentials, database connection, Java, Python or Allure CLI.

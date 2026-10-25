# ADR-0007: Shared store infrastructure and Products publication

- Status: Accepted; supersedes ADR-0006 ownership and updates ADR-0005 image-build authentication
- Date: 2026-10-25

## Context

The educational store now keeps all Azure infrastructure in one simple Terraform
root. Its shared storage account already contains the private `livedocs` container,
and Products has uploaded and read back a real, validated BDD source bundle.
The first report does not require extra Azure identities or a GitHub import App.

## Decision

ECommerceStore.Terraform owns the ACA environment, LiveDocs app and private
`stecproductsdevmb261013/livedocs` container. Do not apply the previous dedicated
LiveDocs Terraform roots to these resources. Existing archives in other accounts
are not moved, deleted or adopted by this change.

Select the Products reference from successful master workflow run 40205595842 in
the development v1 manifest. Image CI reads its immutable archive using repository
secret `LIVEDOCS_STORAGE_SAS_TOKEN`, scoped to the private container. Azure CLI
receives the SAS through its environment, outside Docker. Read permission is
sufficient for these direct downloads; no list or write permission is required.
Keep the existing protected PR/build environments and reject fork archive reads.
The shared helper still supports an existing Azure login when no SAS is provided.

The source bundle, checksum and identity must validate before Allure generation.
CI builds, smoke-tests and scans the static image before publication. Deployment
remains a manual digest update and apply in the shared Terraform root. The runtime
has no Blob connection, credentials, Java, Python or Allure toolchain.

The optional importer remains off and keeps its existing OIDC/GitHub App setup.
Manual manifest PRs are sufficient for this first publication. Released versions
remain immutable; a producer upload alone never changes a running report.

## Consequences

There are no additional Azure resources for Products documentation. CI requires
the SAS secret in LiveDocs as well as Products; expiry or missing archive inputs
blocks rebuilds while an already deployed image keeps serving its snapshot.
The container is private, but documentation baked into the public image and ACA
is public. Preserve referenced blobs and the shared account when cleaning up the
demo: a full shared-root destroy also removes the documentation archive.

## Alternatives considered

- Add dedicated archive infrastructure and reader identities: extra setup for the educational store.
- Fetch reports in running replicas: adds mutable content and runtime storage credentials.
- Commit generated Allure HTML: duplicates rebuildable output in Git.
- Enable the optional importer now: unnecessary App and discovery setup for one known reference.

# ADR-0005: Blob-backed producer integration

- Status: Accepted for LD/5
- Date: 2026-10-05

## Context

Products already generates Reqnroll/Allure results and executable API descriptions.
LiveDocs needs durable, verifiable inputs without service-to-service GitHub writes
or a runtime dependency on Azure Blob.

## Decision

Provide commit-pinned reusable workflows for packaging and archiving producer
inputs. Products packages actual CI exports/results before its quality gate and
archives only after its scanned service image succeeds on master. Content-addressed
ZIPs and immutable discovery receipts live in the private `livedocs` container.
Retries verify existing bytes and refuse replacement.

A main-owned LiveDocs importer discovers candidates, checks successful producer
run provenance and package integrity, and opens a manifest PR using a GitHub App
scoped only to LiveDocs. It neither merges nor deploys. Scheduled discovery is
opt-in; manual import shares the same checks. Released versions remain frozen.

Fetch private inputs with OIDC outside Docker, scoped to the archive container.
Protect PR archive access with a reviewer-controlled GitHub environment; do not
trust the unrestricted pull_request OIDC subject. Build/import federation uses
a separate environment with explicit branch restrictions. Infrastructure owns
all resources, identities, federation and deployment. The final image stays static.

## Consequences

Git history holds small reviewable manifests; Blob holds durable test evidence.
Source commits connect service images and documentation, while image digests
preserve exact generated output. Storage loss blocks rebuilds but does not affect
an already deployed image. GitHub App/environment and Azure setup are prerequisites
for live publication/import. A PR with private inputs requires archive-read review.
These operations do not make service/documentation publication atomic.

## Alternatives considered

- Commit generated reports and attachments: grows Git history with rebuildable data.
- Producer writes into LiveDocs: needs cross-repository GitHub write permission.
- Runtime archive access: adds availability and authentication dependencies to hosting.
- Default GITHUB_TOKEN for PR creation: suppresses the expected PR CI trigger.

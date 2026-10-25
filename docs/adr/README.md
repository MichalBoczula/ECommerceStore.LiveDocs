# Architecture Decision Records

These records describe implemented decisions. A later ADR can supersede an earlier
choice while retaining the record and its number.

Use repository-local, sequential ADR numbers. Each record has a title, `Status`
and `Date` metadata, then `Context`, `Decision`, `Consequences` and
`Alternatives considered` sections in that order. Add new decisions to this index.
Backlog task numbers are separate from ADR numbers.

| ADR | Status | Decision |
| --- | --- | --- |
| [0001](0001-static-container-delivery.md) | Accepted; deployment ownership refined by 0003 | Stateless non-root Nginx host and immutable image publication |
| [0002](0002-versioned-documentation.md) | Accepted | Validated archive inputs and retained Allure project/version snapshots |
| [0003](0003-application-owned-deployment.md) | Ownership superseded by 0006 | Application Infrastructure owns Terraform and Azure deployment |
| [0004](0004-ci-and-verification.md) | Accepted | Portable verification, evidence, security and quality gates before publication |
| [0005](0005-producer-archive-integration.md) | Accepted for LD/5; build authentication and ownership updated by 0007 | Reviewed Blob-backed producer integration |
| [0006](0006-dedicated-terraform-ownership.md) | Ownership superseded by 0007 | Dedicated LiveDocs Terraform repository with persistent archive and disposable hosting roots |
| [0007](0007-shared-store-products-publication.md) | Accepted | Shared store infrastructure, SAS build inputs and the first Products snapshot |

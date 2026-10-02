# ADR-0003: Persistent archive foundation and Terraform app ownership

- Status: Accepted for LD/3 implementation; Azure execution pending
- Date: 2026-10-02

## Context

D/2 bootstrap has not been executed and no ACA environment/identity exists yet.
Application infrastructure is temporary and destroyed when unused. Documentation
packages and deployment access must survive that teardown. An app created only by
LiveDocs CLI would be absent from Infrastructure's Terraform state.

## Decision

Use the existing external Terraform account with a dedicated LiveDocs foundation
container/key. A separate local-operator Terraform root owns archive storage,
identity/federation and delivery permissions. Read retained bootstrap/application
groups as data; protect archive resources and never change the shared backend's
ownership or retention configuration.

Grant CI read-only Blob access and main-branch OIDC. Enable app/environment-scoped
permissions only after Infrastructure has created those resources. Infrastructure
consumes the `infra/app` module and owns app lifecycle and host settings. CI changes
only image/revision; Terraform ignores only those two fields. Deployment checks the
existing host and refuses to create an untracked app or repair host drift.

Private packages are fetched outside Docker only on trusted main runs. PR/feature
builds use isolated fixture inputs when production references exist. Publication
requires complete real input validation on main; Docker receives no credentials.

## Consequences

Fresh setup is D/2 foundation, persistent LiveDocs foundation, Infrastructure
environment/app, scoped grants, readiness verification and immutable rollout.
Subscription/tenant variables alone cannot trigger provisioning. All shared
infrastructure changes stay in their owning repository.

Before application Destroy, disable delivery and revoke ephemeral-scope grants
through the persistent foundation. The archive/identity remain; reapply restores
app resources and grants. Locks protect management-plane deletion; versioning and
soft delete aid data recovery without becoming a tested backup guarantee.

CI runs provider/mocked tests without Azure. Live OIDC, storage and deployment
checks remain explicitly pending until the user runs bootstrap in Azure.

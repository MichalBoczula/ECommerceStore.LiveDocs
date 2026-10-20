# ADR-0006: Dedicated LiveDocs Terraform ownership

- Status: Accepted; supersedes deployment ownership in ADR-0003 and updates ADR-0005 setup
- Date: 2026-10-20

## Context

The application now uses dedicated Products, BFF and web Terraform repositories.
The former ECommerceStore.Infrastructure repository is deprecated. LiveDocs needs
independent infrastructure ownership while its archive must survive temporary
portfolio hosting teardown.

## Decision

ECommerceStore.LiveDocs.Terraform owns Azure provisioning and manual rollout in
two separate roots and remote state keys. `archive/` retains a dedicated private
Blob account/container and CI writer/reader identities. `hosting/` deploys a
digest-pinned static Nginx image into the shared application ACA environment.
The environment and network remain owned by the Products Terraform stack.

The application repository continues to own generation, manifests, archive/import
tooling, tests, and scanned Docker Hub image publication. It does not gain an ACA
deployment workflow. CI alone reads archive inputs; the runtime has no Blob
mount, download, Azure identity, database or Allure build toolchain.

Any applied legacy archive must be adopted through a reviewed state/resource
migration preserving its account and retained URLs. A new repository does not
automatically move ownership or justify a second owner for the same resource.

## Consequences

The demo host can be removed without deleting rebuild inputs. Public hosting is
explicit; private Blob access does not make content embedded in public images
confidential. Protected GitHub environments and the import App remain setup
requirements. New reports still require a manifest PR, image publication and a
reviewed Terraform apply; Blob uploads do not update running replicas.

## Alternatives considered

- Keep using the deprecated application infrastructure root: retains stale ownership.
- Share the disposable Products photo account: couples documentation retention to demo teardown.
- Fetch reports at runtime: adds credentials, storage availability and mutable replica content.

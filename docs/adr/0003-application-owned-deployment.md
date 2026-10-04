# ADR-0003: Application-owned deployment

- Status: Accepted for LD/3
- Date: 2026-10-04

## Decision

LiveDocs owns documentation manifests, generation, its static host and Docker Hub
publication. ECommerceStore.Infrastructure owns all Terraform and deploys LiveDocs
with the whole application, including resource creation, updates and destruction.
Storage, identities, registry access, ingress, probes and scaling belong there.

LiveDocs CI ends after publishing a tested, scanned image and its immutable digest.
It does not log into Azure, create resources or update an ACA revision. The
[container contract](../container-contract.md) supplies the deployment interface.

## Consequences

Application rollout selects a published digest through Infrastructure. LiveDocs
needs only Docker Hub credentials for publication. Its container has no required
Azure configuration, runtime secrets or service dependencies. Producer integration
remains LD/4 and must provide verified build inputs before image publication.

This decision replaces the Azure delivery ownership described in ADR-0001 and the
LD/3 archive-access setup described in ADR-0002. Archive tooling remains a data
interface; provisioning and access lifecycle belong to application Infrastructure.

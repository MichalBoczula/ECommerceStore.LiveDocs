# ADR-0001: Static container and immutable delivery

- Status: Accepted for LD/1
- Date: 2026-10-02

## Context

ProductsCatalog already produces executable BDD documentation and structured
API/flow/validation sources. LiveDocs needs one host for those services and future
releases, published to the user's Docker Hub and deployed to Azure Container Apps.

## Decision

Serve files baked into a non-root Nginx container on port 8080. Build and validate
the image in CI; smoke-test and scan it before publishing the same image to
`mb0101/ecommerce-store-livedocs`. Keep commit tags and deploy by image digest.

Application Infrastructure deploys the published image with the other services
and owns Terraform, ACA resources, ingress, probes and scaling. The app host is
independent of service APIs. Readiness checks the assembled site marker; rollout
verification can check the baked-in source commit.

This repository owns the host and image publication. Git stores sources,
configuration and version manifests; generated reports and attachments remain
outside Git. See ADR-0003 and the container contract for deployment ownership.

## Consequences

Replicas do not mutate their documentation files. Restarts and new revisions serve
the same snapshot. Report publication will rebuild the container. LD/2 must preserve
released manifests and include the selected historical versions in each snapshot.

LD/1 contains an honest empty portal. LD/2 adds Allure 2 generation, durable
artifact tooling and versioned navigation (see ADR-0002). LD/3 defines the image handoff to application Terraform; producer CI integration
is LD/4.

The current base image tag floats to receive maintenance, and the build applies
available Alpine distribution package updates before smoke testing and scanning.
Published images are immutable by digest. If byte-for-byte build reproduction
becomes necessary, introduce a maintained base-digest and package update policy.

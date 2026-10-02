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

Use an existing ACA environment with OIDC delivery, explicit health probes,
public HTTPS and HTTP scale-to-zero. The app host is independent of the service
APIs. Readiness checks the assembled site marker; public rollout verification
checks the baked-in source commit.

The repository owns the host and dedicated app configuration, not the shared
resource group/environment. Git stores sources/configuration and later version
manifests; generated reports/attachments remain outside Git.

## Consequences

Replicas do not mutate their documentation files. Restarts and new revisions serve
the same snapshot. Report publication will rebuild the container. LD/2 must preserve
released manifests and include the selected historical versions in each snapshot.

LD/1 contains an honest empty portal. Allure 3 generation, durable artifacts,
versioned project navigation and producer CI integration are separate tasks.

The current base image tag floats to receive maintenance, and the build applies
available Alpine distribution package updates before smoke testing and scanning.
Published images are immutable by digest. If byte-for-byte build reproduction
becomes necessary, introduce a maintained base-digest and package update policy.

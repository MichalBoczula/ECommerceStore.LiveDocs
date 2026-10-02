# ECommerceStore LiveDocs

LiveDocs is the central documentation portal for the ECommerceStore services.
It will combine executable BDD scenarios and Allure reports with generated
OpenAPI contracts, business flows and validation policies.

## Current scope: LD/1

This repository provides a stateless Nginx container, local Compose setup,
host health checks, container smoke tests, Docker Hub publication and a
configurable Azure Container Apps deployment workflow.

The initial `/livedoc/` page states that no reports have been published. Allure
generation, versioned service routes and manifests are LD/2. Producer CI
integration is LD/3. No fake report or passing test status is included.

## Architecture and ownership

- Service repositories own their tests and generated documentation sources.
- LiveDocs will assemble approved artifacts into an immutable image snapshot.
- Nginx serves baked-in files on port **8080**, as UID/GID **101:101**.
- ACA uses public HTTPS ingress, explicit startup/readiness/liveness probes,
  **0.25 vCPU / 0.5 GiB**, and HTTP scaling from **0 to 1 replica**.
- Git contains code, configuration and eventually manifests. Generated reports
  and attachments are not committed; durable artifact storage is LD/2.
- Shared resource groups and ACA environments remain owned by the portfolio
  infrastructure. This pipeline creates or updates only the dedicated LiveDocs app.

See [ADR-0001](docs/adr/0001-static-container-delivery.md).

## Local development

Requirements: Docker with Compose, Bash and Python 3. No Python dependencies,
.NET SDK, Java, SQL Server or Allure installation are required for LD/1.

```bash
docker compose up --build --detach
python3 scripts/smoke.py http://127.0.0.1:8080 --expected-sha local
docker compose down
```

Open http://localhost:8080/livedoc/.

Full local verification:

```bash
bash scripts/verify.sh
```

The smoke test starts the actual image with a read-only root filesystem,
temporary `/tmp`, dropped capabilities and no-new-privileges. It checks redirects,
HTML/CSS, health, missing paths and commit identity. A second container with its
site hidden must return readiness **503** while remaining live.

## HTTP contract

| Path | Behavior |
| --- | --- |
| `/` | Redirect to `/livedoc/` |
| `/livedoc` | Redirect to `/livedoc/` |
| `/livedoc/` | Initial portal page |
| `/health/live` | Host is responding |
| `/health/ready` | Baked-in content marker exists |
| `/build-info.json` | Commit SHA and build timestamp |
| Unknown paths/assets | HTTP 404; no SPA fallback |

LD/2 adds `/livedoc/v1/products/`, `/livedoc/v1/users/` and further project/version
paths. Host readiness does not imply any service report or upstream API is healthy.

## CI and Docker Hub

The workflow runs on PRs, pushes to `main` and manual dispatch:

1. Run regression checks and validate Bash/Compose.
2. Build once, smoke-test the actual container and scan it with Trivy.
3. On `main`, publish the same tested/scanned image to Docker Hub:
   - `mb0101/ecommerce-store-livedocs:latest`;
   - `mb0101/ecommerce-store-livedocs:<full-commit-sha>`.
4. Deploy by digest when Azure delivery is configured and enabled.

Required repository **secrets**:

| Secret | Purpose |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub account with write access to `mb0101/ecommerce-store-livedocs` |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

The Docker Hub repository must be **public** for the credential-free ACA pull
implemented here. PRs never publish or authenticate to Azure. The base image uses
the maintained `stable-alpine` tag and applies available Alpine package updates
before testing/scanning; each published output is fixed by its digest.

## Azure delivery

See [Azure setup and rollout](docs/azure-deployment.md) for OIDC and variables.
Azure deployment is disabled until `AZURE_DEPLOY_ENABLED=true` is configured.
Docker Hub publication works independently of that setting.

After configuring Azure, run **LiveDocs CI and delivery** on `main` with the
`deploy` input enabled for the first deployment, or enable automatic deployment
after successful publication. Missing configuration fails an explicitly requested
deployment before Azure login.

The workflow summary records the image digest, deployed commit and portal URL.
Deployment success requires the public HTTPS smoke check to serve the expected
commit, not just a successful Azure CLI command.

## Roadmap

| Task | Deliverable |
| --- | --- |
| LD/1 | Static container, checks, Docker Hub and configurable ACA delivery |
| LD/2 | Versioned project manifests, artifact archive, Allure 3 generation and documentation pages |
| LD/3 | Shared producer publication workflow, Products first, then other services |

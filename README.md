# ECommerceStore LiveDocs

LiveDocs assembles BDD scenarios, Allure results, OpenAPI contracts, business flows
and validation policies into one stateless documentation container. Service
repositories own the sources; this repository owns manifests, generation, the static
host and image publication. Application Terraform owns Azure deployment.

## Current scope: LD/3 image handoff

LiveDocs supplies an application image which serves all selected documentation.
[ECommerceStore.Infrastructure](https://github.com/MichalBoczula/ECommerceStore.Infrastructure)
creates the infrastructure in Terraform and deploys LiveDocs with the whole
application. There is no Azure provisioning, deployment workflow or deployment
identity in this repository. See the [container contract](docs/container-contract.md)
for the image, port, probes, filesystem and immutable digest interface.

Each manifest version contains independent project snapshots. For example,
`/livedoc/v1/products/` and `/livedoc/v1/users/` coexist with `/livedoc/v2/products/`.
Adding a registered project requires a manifest entry, not an Nginx configuration
change. Development versions can advance; released versions cannot be changed or
removed by a subsequent PR.

**Allure 2.46.1** is pinned with its official distribution SHA-256 in
[`tools/allure.json`](tools/allure.json). ProductsCatalog documents
`allure-commandline@2` and uses Allure.Reqnroll 2.14.1 with Reqnroll.xUnit 3.3.0.
The CLI and .NET adapter have independent version numbers; both use Allure 2
results. Products' CLI pin will be aligned during LD/4.

The production manifest intentionally has an empty development `v1` until producer
integration. CI uses clearly labelled, isolated fixtures for Products and Users at
v1 and Products at v2, including a failed test.

## Snapshot architecture

1. Stage sources and raw Allure results in a validated ZIP package.
2. Archive the package in durable Azure Blob storage at a content-addressed path.
3. Commit its URL, checksum, size, source commit and workflow run to a version manifest.
4. Generate all retained versions with the pinned Allure CLI and bake the completed
   portal into the image. Invalid or missing packages fail the build.
5. Smoke-test and scan the image, then publish to Docker Hub. Application Terraform
   deploys the selected digest with the other services.

Git stores manifests and code. Packages, generated reports and attachments stay
outside Git. The final Nginx container runs as **101:101** on **8080** and contains
no Java, Python or Allure installation. Replicas never modify their documentation.

See [artifact contract and publication](docs/artifact-contract.md),
[ADR-0001](docs/adr/0001-static-container-delivery.md) and
[ADR-0002](docs/adr/0002-versioned-documentation.md).

## Local development

Requirements: Docker with Compose, Bash and Python **3.12+**. Docker installs Java,
Allure and build dependencies in its builder stage.

```bash
docker compose up --build --detach
python3 scripts/smoke.py http://127.0.0.1:8080 --expected-sha local
docker compose down
```

Open http://localhost:8080/livedoc/.

Full source and container verification:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
bash scripts/verify.sh
```

Verification builds production and fixture images. Real HTTP checks cover version
and project routes, Allure assets, JSON, test cases, attachments, missing paths and
commit identity. The runtime must remain non-root and work with a read-only root
filesystem. Hiding the site must return readiness **503** while the host remains live.

## HTTP contract

| Path | Behavior |
| --- | --- |
| `/` or `/livedoc` | Redirect to `/livedoc/` |
| `/livedoc/` | Version navigation |
| `/livedoc/latest/` | HTML redirect to the selected latest version |
| `/livedoc/v1/` | Projects published in that version |
| `/livedoc/v1/products/` | Provenance, BDD, API, flows and rules when published |
| `/livedoc/v1/products/allure/` | Allure report with its own relative assets and data |
| `/livedoc/catalog.json` | Selected versions and artifact references |
| `/health/live` | Host is responding |
| `/health/ready` | Baked-in content marker exists |
| `/build-info.json` | LiveDocs commit SHA and build timestamp |
| Unknown paths/assets | HTTP 404; no SPA fallback |

Project pages link to downloadable source JSON and bundle metadata. Host readiness
does not imply a passing BDD suite or a healthy upstream service API.

## CI and Docker Hub

PRs, pushes to `main` and manual dispatch run manifest/regression checks, real
Allure fixture generation and container HTTP checks. CI compares released manifests
with the prior revision. The production image is built once, smoke-tested and scanned
with Trivy. That same image is published on `main` to:

- `mb0101/ecommerce-store-livedocs:latest`;
- `mb0101/ecommerce-store-livedocs:<full-commit-sha>`.

Required repository **secrets**:

| Secret | Purpose |
| --- | --- |
| `DOCKERHUB_USERNAME` | Account with write access to the Docker Hub repository |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

The Docker Hub repository must be public for credential-free pulls. PRs never
publish; main publication requires the real production inputs. CI also uploads
`livedocs-image/image.json` with the published digest, commit and build timestamp.
Nginx applies available Alpine fixes before scanning. Infrastructure selects the
published digest for rollout; LiveDocs needs no subscription, tenant or Azure identity.

Private archived inputs can be prefetched outside Docker into `build-input/cache`
using the data tools in [the artifact contract](docs/artifact-contract.md).
Automated private input retrieval remains part of LD/4 producer integration and
must be configured before adding private production references. Current CI does
not sign into Azure; unavailable inputs fail the build. No credentials or SAS URLs
enter Docker or Git.

## Ownership and roadmap

See [ADR-0003](docs/adr/0003-application-owned-deployment.md). Application
Infrastructure owns Azure resources and the deployment lifecycle, including any
archive storage and access grants. This repository publishes the image.

| Task | Deliverable |
| --- | --- |
| LD/1 | Static container, health checks and Docker Hub publication — implemented |
| LD/2 | Versioned manifests, archive tooling, Allure 2 generation and documentation pages — implemented |
| LD/3 | Image-only publication and documented Terraform consumption contract |
| LD/4 | Producer CI integration and verified build inputs, Products first |

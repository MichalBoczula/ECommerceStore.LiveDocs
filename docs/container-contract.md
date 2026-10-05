# LiveDocs container contract

LiveDocs builds and publishes the documentation image. The
[application Infrastructure repository](https://github.com/MichalBoczula/ECommerceStore.Infrastructure)
owns Terraform, Azure resources and deployment together with the other services.
LiveDocs has no independent Azure deployment workflow or deployment identity.

## Image and publication

CI builds once, checks the actual container and scans it before publishing the same
image to `mb0101/ecommerce-store-livedocs`. Main publishes `latest` and a full
LiveDocs commit SHA tag. PRs validate the image without publishing.

Use the immutable `mb0101/ecommerce-store-livedocs@sha256:<digest>` reference from
the successful publication job summary as Terraform's image input. The same run
uploads `livedocs-image/image.json` as a GitHub Actions artifact:

```json
{
  "schemaVersion": 1,
  "image": "mb0101/ecommerce-store-livedocs@sha256:<digest>",
  "commitSha": "<full LiveDocs commit SHA>",
  "builtAt": "<UTC build timestamp>"
}
```

This metadata identifies an already published image; it is not a durable archive
of documentation inputs. Infrastructure chooses when to roll out that digest.
Keep the Docker Hub repository public for credential-free image pulls; private
registry authentication, if selected, belongs to Infrastructure.

## Runtime interface

| Setting | Contract |
| --- | --- |
| Protocol and port | HTTP on TCP 8080; terminate public TLS at application ingress |
| User | Non-root UID/GID `101:101` |
| Entrypoint | Base image Nginx startup; no command override needed |
| Startup/liveness probe | HTTP GET `/health/live` on 8080 returns 200 |
| Readiness probe | HTTP GET `/health/ready` on 8080 returns 200 with the site marker, 503 without it |
| Identity | GET `/build-info.json` returns `commitSha` and `builtAt` |
| Configuration | No required environment variables or secrets |
| Persistence | No volume, database or service API connection required |
| Filesystem | Supports read-only root with writable `/tmp` for Nginx temporary files |
| Logs | Nginx stdout/stderr |
| Resources/scaling | CPU, memory, replica counts and probe timing are chosen in application Terraform |

ACA needs explicit probes; do not rely on the Docker `HEALTHCHECK` being imported.
The host can start independently of Products, Users and other service APIs.
Readiness indicates documentation availability, including failed BDD results.
After rollout, compare `/build-info.json` with the selected image's LiveDocs commit.

## Content and build inputs

The image contains all retained manifest versions. Routes include `/livedoc/`,
`/livedoc/v1/products/`, `/livedoc/v1/users/` and `/livedoc/v2/products/` when those
snapshots are published. Each project has its own `allure/` report. Unknown paths
return 404. Preserve the `/livedoc/` prefix through ingress so report assets resolve.

Reports are assembled in the Docker builder stage using pinned Allure 2.46.1;
the runtime contains only Nginx and static content. Deploying an image cannot add
reports to it. Updated manifests and source bundles require a new image build.

Build arguments `MANIFEST_DIRECTORY` and `ARTIFACT_DIRECTORY` select manifests
and verified ZIP inputs in the build context, defaulting to `manifests` and
`build-input/cache`. `VCS_REF` and `BUILD_DATE` supply image identity. Never pass
credentials as build arguments. See [the artifact contract](artifact-contract.md).

The initial production manifest has an empty development v1. Producer integration,
Products first, remains LD/5. Private archive retrieval must be wired into the
build-input pipeline before adding private references to production manifests;
missing inputs fail the build. Infrastructure owns any storage and access grants.

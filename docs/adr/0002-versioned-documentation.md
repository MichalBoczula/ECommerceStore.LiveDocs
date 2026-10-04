# ADR-0002: Versioned Allure 2 documentation snapshots

- Status: Accepted for LD/2
- Date: 2026-10-02

## Context

The portal must retain multiple service snapshots and release versions. Products
uses the Allure 2 CLI family and Allure.Reqnroll adapter. Azure deployment precedes
producer integration, so the host must support an honest empty manifest.

## Decision

Pin Allure CLI 2.46.1 and its official distribution checksum. Generate reports in
the Docker builder stage and serve with the stateless Nginx runtime. Use
`/livedoc/<version>/<project>/` for documentation and `allure/` beneath each project.
A project registry and strict portal/bundle schemas define the inputs.

Archive source packages in content-addressed Azure Blob paths. Store stable URLs,
SHA-256, size, source commit, timestamp and workflow identity in Git manifests.
Validate archive/file integrity, identity and attachment presence before generation.
Fetch private archives with Azure identity outside Docker. Never commit reports
or credentials.

Development versions can advance. Freeze a version by marking it released; CI
compares with the previous manifest to prevent modification/deletion. Build all
retained versions together. Publish only after complete assembly, real container
checks and scanning. Verify isolated project/version fixtures with a failed result
to ensure generation preserves actual status.

## Consequences

Every replica serves the same complete snapshot, including historical versions.
An unavailable archived input prevents a rebuild without altering the deployed
image. Retention must preserve referenced packages; ACA disk is not the archive.
Archived inputs enable regeneration, while image digests preserve exact generated
output. Allure upgrades require intentional validation.

LD/3 defines the image contract; application Infrastructure owns storage access
and deployment (ADR-0003). LD/5 connects Products first, then other producers.

## Alternatives considered

- Overwrite one latest report: loses release and project history.
- Store generated reports in Git: grows the repository with rebuildable outputs and attachments.
- Rebuild releases from short-lived workflow artifacts: loses required inputs when those artifacts expire.

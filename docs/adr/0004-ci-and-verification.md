# ADR-0004: CI gates and local verification

- Status: Accepted
- Date: 2026-10-05

## Context

LiveDocs should use the repository conventions established in ECommerceStoreInvoice:
a predictable README and ADR index, portable verification commands, separate test
evidence, security checks and an explicit gate before publishing a scanned image.
Its Python generator and static host have different test boundaries from .NET layers.

## Decision

Use `scripts/ci.sh` for source contracts, Python/Bash/Compose checks, Python dependency
audit, assembly/hosting suites, real fixture generation, image build, smoke checks
and publication. Local `scripts/verify.sh` calls the same verification entry points.
GitHub Actions owns dependencies, artifact upload, credentials and scanners.

Run independent build, dependency audit and Gitleaks jobs. Assembly, hosting and
actual documentation container tests depend on build. PRs also require Dependency
Review at high/critical severity. pip-audit checks direct/transitive build and CI
requirements and blocks known advisories. It has no severity exception list.

Assembly and hosting tests emit JUnit XML and Markdown summaries. Empty, failed,
skipped and unexpected-success suites fail. The complete `scripts/livedocs.py`
generator module requires at least 70% line coverage, without excluded lines.
Publish Cobertura and HTML coverage. This gate measures the generator, not all
scripts or the Nginx runtime. Real fixture/container checks independently enforce
Allure version isolation, failure status, attachments, nested HTTP assets,
read-only non-root runtime and missing-content readiness behavior.

An always-running quality gate rejects any failed, cancelled, skipped or missing
mandatory job. Dependency Review is required on PRs and intentionally skipped on
push/manual runs. Image build starts only after the gate succeeds. Build once,
smoke-test, scan fixable high/critical findings with Trivy, then publish the same
local image on main with full commit and latest tags. Both pushes must report the
same immutable digest. Preserve the image metadata contract from LD/3.

LD/4 delivers these conventions; producer integration formerly labelled LD/4 is
now **LD/5**, Products first. No service tests, Infrastructure files, Azure resources
or runtime dependencies change here.

## Consequences

Failed checks block image publication. Artifact and job summaries provide evidence
on PRs; the scripts can be called by another CI orchestrator later. The final image
keeps its existing static runtime and pinned Allure builder. Only Docker Hub
credentials are needed for publication. Azure provisioning/deployment stay in
application Infrastructure.

Python 3.12+, CI requirements, Bash and Docker are required for full local checks.
Local verification does not replace Gitleaks, PR Dependency Review or the Trivy
image gate. Automated private archive retrieval remains LD/5 and must be configured
before private input references are added to production manifests.

## Alternatives considered

- Duplicate local checks in workflow YAML: allows local and remote behavior to drift.
- Copy the .NET suite names and thresholds to every script: hides the actual generator and HTTP test boundaries.
- Allow skipped mandatory jobs to pass: can publish without complete verification.
- Rebuild after scanning: can publish bytes different from the tested image.

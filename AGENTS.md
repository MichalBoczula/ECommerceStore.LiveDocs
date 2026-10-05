# Agent instructions

Read [README.md](README.md), [Definition of Done](docs/definition-of-done.md) and the relevant [ADRs](docs/adr/README.md) before editing. Keep commits and PR descriptions in English and scope changes to the requested work.

## Scope

- LiveDocs owns the static documentation host and its image publication pipeline. Service repositories own BDD tests, OpenAPI, flows and validation rules.
- LD/1 provides the container, Compose, host checks and Docker Hub publication. LD/2 adds Allure 2 generation, version manifests and archive tooling. LD/3 defines the image contract for application Terraform. LD/4 aligns README/ADRs and shared CI verification; LD/5 integrates producers, Products first.
- Preserve a stateless runtime: generated documentation is assembled before image creation. Never upload reports into a running replica.
- Do not commit generated reports, test attachments, credentials or production payloads. Do not change service repositories, shared Terraform or GitHub secrets as incidental cleanup.
- ECommerceStore.Infrastructure owns all Terraform, Azure resources, identities, storage access and deployment together with the application. LiveDocs CI ends at image publication; do not add separate Azure provisioning, login or revision-update workflows here. Preserve the interface in `docs/container-contract.md`.

## Verification

Install `requirements-ci.txt` with Python 3.12+ and run `bash scripts/verify.sh` with Docker and Bash. It validates manifests and regressions, builds production and fixture images, and checks actual Nginx HTTP behavior. Use `bash scripts/ci.sh source`, `build`, `audit`, `test assembly`, `test hosting` or `test documentation` for focused CI-equivalent checks. The workflow calls those entry points.

Preserve released versions and archived inputs. Keep Allure pinned in `tools/allure.json`; its CLI version is independent of the Allure.Reqnroll adapter version. Never add CI fixtures to production manifests.

Do not skip required checks, use `continue-on-error`, or lower security/coverage gates to make CI green. The generator module has a 70% line coverage floor with no exclusions; do not claim this covers every script or Nginx. Required suites must run nonzero tests without failures or skips.

CI smoke-tests and scans the built image before publishing that same image. Publication emits an immutable digest and image metadata for Infrastructure. Never hide failed checks or claim an unrun check passed. Keep private archive credentials outside Docker; LD/5 must supply verified inputs before real private manifest references are added.

## Delivery

Use a feature branch and PR. Report behavior, verification, remaining setup and scope limitations. Initializing an empty repository with a minimal README is allowed so a PR can be opened.

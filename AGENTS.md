# Agent instructions

## Scope

- LiveDocs owns the static documentation host and its delivery pipeline. Service repositories own BDD tests, OpenAPI, flows and validation rules.
- LD/1 provides the container, Compose, host checks and Docker Hub publication. LD/2 adds Allure 2 generation, version manifests and archive tooling. LD/3 configures Azure storage and deploys ACA; LD/4 integrates producers, Products first.
- Preserve a stateless runtime: generated documentation is assembled before image creation. Never upload reports into a running replica.
- Do not commit generated reports, test attachments, credentials or production payloads. Do not change service repositories, shared Terraform or GitHub secrets as incidental cleanup.
- Deploy to an existing Azure Container Apps environment. `infra/foundation` owns persistent archive/identity resources in a separate remote state. `infra/app` is consumed by Infrastructure application state, which owns app creation/deletion and host configuration. LiveDocs CI updates only image/revision. Do not create shared environments or application groups here.

## Verification

Install `requirements-build.txt` with Python 3.12+ and run `bash scripts/verify.sh` with Docker and Bash. It validates manifests and regressions, builds production and fixture images, and checks actual Nginx HTTP behavior. Run `python3 -m unittest discover -s tests -v` for source regression tests.

Preserve released versions and archived inputs. Keep Allure pinned in `tools/allure.json`; its CLI version is independent of the Allure.Reqnroll adapter version. Never add CI fixtures to production manifests.

CI smoke-tests and scans the built image before publishing that same image. Deployment uses an immutable image digest and verifies the deployed commit identity. Never hide failed checks or claim an unrun check passed.

Run pinned Terraform formatting, backend-disabled validation and mocked tests for both `infra/foundation` and `infra/app`. No CI test logs into Azure; readiness is an explicit main-only workflow after local bootstrap. Keep provider locks committed and raw plans/state outside Git. Fresh setup must leave automatic deployment disabled.

## Delivery

Use a feature branch and PR. Report behavior, verification, remaining setup and scope limitations. Initializing an empty repository with a minimal README is allowed so a PR can be opened.

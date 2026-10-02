# Agent instructions

## Scope

- LiveDocs owns the static documentation host and its delivery pipeline. Service repositories own BDD tests, OpenAPI, flows and validation rules.
- LD/1 provides the container, Compose, host checks, Docker Hub publication and ACA deployment. Report generation, version manifests and producer integration belong to LD/2 and LD/3.
- Preserve a stateless runtime: generated documentation is assembled before image creation. Never upload reports into a running replica.
- Do not commit generated reports, test attachments, credentials or production payloads. Do not change service repositories, shared Terraform or GitHub secrets as incidental cleanup.
- Deploy to an existing Azure Container Apps environment. This repository manages its dedicated container app, not the shared environment or resource group.

## Verification

Run `bash scripts/verify.sh` from the repository root with Docker, Python 3 and Bash. It validates the source, builds the image and checks the actual HTTP behavior of Nginx. Run `python3 -m unittest discover -s tests -v` for deployment and smoke-check regression tests.

CI smoke-tests and scans the built image before publishing that same image. Deployment uses an immutable image digest and verifies the deployed commit identity. Never hide failed checks or claim an unrun check passed.

## Delivery

Use a feature branch and PR. Report behavior, verification, remaining setup and scope limitations. Initializing an empty repository with a minimal README is allowed so a PR can be opened.

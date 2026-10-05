# Definition of Done

Apply these checks where relevant; this checklist does not claim every possible
path already has test coverage.

- The PR describes resulting behavior and scope, names the backlog task and records actual validation and limitations.
- Generation preserves project/version isolation, bundle/file identity and integrity, required attachments, safe archive extraction and atomic output. Released manifests remain immutable.
- The final image stays stateless, non-root and free of the build toolchain. Its real HTTP checks verify routes, assets, 404s, health endpoints and selected commit identity.
- Run focused `scripts/ci.sh` checks; run `scripts/verify.sh` when prerequisites are available. Report unavailable checks honestly. Required suites run nonzero tests without failures or skips and retain a 70% floor for the whole generator module with no exclusions.
- Build, assembly, hosting, documentation, dependency audit and secret scanning succeed. PR Dependency Review must succeed. Do not use `continue-on-error`, skip jobs or lower security/coverage gates to obtain a green result.
- The image job starts after the explicit quality gate, smoke-tests and scans its one built image, then publishes those same bytes on main. SHA/latest tags report one digest and image metadata identifies the source commit.
- Update README, contracts and the ADR index when behavior or decisions change. Preserve repository-local ADR numbers and the shared record format.
- Keep generated reports, test fixtures, credentials and production payloads out of Git. Private archive credentials stay outside Docker. Azure resources and deployment belong to application Infrastructure; producer integration is LD/5.

The PR is ready to merge when applicable checks pass and remaining limits are recorded.

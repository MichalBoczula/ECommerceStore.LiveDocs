# Local verification

Install Python 3.12+, Bash, Docker with Compose and a running daemon, then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-ci.txt
bash scripts/verify.sh
```

`verify.sh` runs **Source**, **Build**, **Assembly**, **Hosting**, **Documentation**,
**Dependency audit**, **Image** and **Production HTTP** in order. It exits at the
first failed stage, with the stage name and exit code. Docker installs Java and
Allure in the builder; the host does not need them.

Both local verification and Actions call `scripts/ci.sh`:

| Command | Checks |
| --- | --- |
| `source` | Manifests and previously released version immutability |
| `build` | Python compilation, Bash syntax and Compose configuration |
| `test assembly` | Package/generation regressions, JUnit evidence and 70% generator line coverage |
| `test hosting` | HTTP smoke checker, required quality jobs and publication boundary regressions |
| `test documentation` | Actual Allure fixture image, provenance/status isolation and Nginx HTTP checks |
| `audit` | Direct/transitive requirements audited by pip-audit; known findings fail |
| `image` | Build the production image as `ecommerce-store-livedocs:ci` |
| `smoke ecommerce-store-livedocs:ci` | Production HTTP, image identity, non-root/read-only behavior and readiness |

`BASE_SHA` selects a previous manifest commit; Actions supplies the PR base or
previous push SHA. Local/manual runs fall back to `HEAD^` when available.
`VCS_REF` and `BUILD_DATE` default to `local` and identify built images.
`VERIFY_RESULTS_DIR` overrides the default artifact root, and
`VERIFY_SUMMARY_FILE` selects a Markdown summary path. The scripts create their
artifact directories and clear previous suite results before rerunning that suite.
Local `verify.sh` clears the combined summary at the start.

| Output | Default path |
| --- | --- |
| Assembly JUnit results | `artifacts/verification/assembly/results.xml` |
| Generator coverage | `artifacts/verification/assembly/coverage.cobertura.xml` and `coverage/index.html` |
| Hosting JUnit results | `artifacts/verification/hosting/results.xml` |
| Fixture site/evidence | `artifacts/verification/documentation/site-*/` and `result.txt` |
| Dependency audit | `artifacts/verification/dependency-audit.json` |
| Combined local summary | `artifacts/verification/summary.md` |
| Published image metadata (main CI only) | `artifacts/verification/image.json` |

Required Python suites must run at least one test, without errors, failures or
skips. The generator coverage scope is all of `scripts/livedocs.py`, with no lines
excluded. Coverage does not establish correct HTTP behavior; the actual container
checks remain required. Missing coverage data and failed report generation fail.

CI additionally requires Gitleaks, PR Dependency Review, its explicit quality gate
and a high/critical Trivy image scan. Local `verify.sh` never logs into Docker Hub
or publishes an image. Actions runs `ci.sh publish` only after successful scan
and login on main; the command also refuses PR/feature contexts. Docker Hub
credentials are supplied by the workflow, not by the scripts.

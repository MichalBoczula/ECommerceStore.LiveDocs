# Documentation artifacts and version manifests

## Package layout

Stage these inputs at the ZIP root. Allure results must be flat within
`allure-results/`, including result/container JSON and referenced attachments.
Preserve feature files and relative paths under `bdd/`.

```text
bundle.json
sources/openapi.json
sources/flows.json
sources/validation-policies.json
sources/operation-links.json
bdd/<feature files>.feature
allure-results/<raw Allure 2 files>
```

`openapi.json` must contain an OpenAPI 3 contract and `paths`. Other sources must
be JSON objects or arrays. At least one feature and one completed Allure result
are required. Failed, broken and skipped results remain visible.

Create a metadata file outside the staged directory:

```json
{
  "schemaVersion": 1,
  "project": "products",
  "repository": "MichalBoczula/ProductsCatalog",
  "commitSha": "<full 40-character source commit SHA>",
  "generatedAt": "2026-10-02T20:00:00Z",
  "workflowRunId": 123
}
```

Replace these example values with actual producer identity. The packaging tool
computes every file's SHA-256 and byte count and writes the inventory into `bundle.json`:

```bash
python3 scripts/package-bundle.py --source artifacts/staged \
  --metadata artifacts/metadata.json --output artifacts/products.zip
```

The contract is enforced by [`bundle.schema.json`](../schemas/bundle.schema.json)
and semantic validation. Undeclared files, mismatched identity, changed bytes,
missing attachments, unsafe paths and duplicate ZIP entries fail validation.
Limits are 100 MiB compressed, 500 MiB expanded and 10,000 ZIP entries.

## Durable archive

Short-lived GitHub Actions artifacts cannot be the source for rebuilding released
documentation. Azure Blob is the durable archive. Account/container creation,
RBAC and retention configuration are LD/3; LD/2 supplies the archive tools.

After Azure CLI login with a Blob Data Contributor identity:

```bash
python3 scripts/archive-bundle.py --file artifacts/products.zip \
  --account YOUR_STORAGE_ACCOUNT --container livedocs \
  --output artifacts/products-reference.json
```

The uploader validates the package and writes it to
`reports/<project>/<source-commit>/<package-sha256>.zip`. Overwrite is disabled;
an existing object produces an upload conflict, rather than being silently trusted.
The reference is written only after successful upload. An upload retry should
reuse the original reference after verifying the existing object's checksum.

URLs are stable HTTPS Azure Blob URLs without SAS parameters or credentials.
Redirects are rejected. The build verifies archive checksum and size, including
cached copies. Retain every package referenced by any supported manifest version.
Do not apply blanket expiry to referenced release packages. Configure Blob
versioning/soft delete and retention in LD/3. Content addressing and disabled
overwrite prevent this publisher from replacing an object, but do not prevent
a storage administrator from deleting it.

For a private container, authenticate outside Docker with a Blob Data Reader
identity and prefetch:

```bash
python3 scripts/fetch-archives.py --azure-auth
docker compose build
```

The cache contains verified `<sha256>.zip` files. For public archives, prefetch
without `--azure-auth`, or let Docker fetch the declared URLs. Never pass Azure
credentials as build arguments. Private archive CI identity and prefetch will be
configured with LD/3 before LD/4 publishes real manifests.

## Registering and updating versions

`manifests/projects.json` maps project slugs to display names and source repositories.
Add future projects there. `manifests/portal.json` chooses the latest version and
lists each version's state and project references:

```json
{
  "schemaVersion": 1,
  "latestVersion": "v1",
  "versions": [
    {"version": "v1", "state": "development", "projects": []}
  ]
}
```

Insert the uploader's complete project reference into the chosen `projects` array.
[`portal.schema.json`](../schemas/portal.schema.json) defines the shape.
Unknown/duplicate projects, duplicate versions and nonexistent latest versions
fail validation. Bundle repository, source commit, timestamp and run must match
the reference and registry.

During development, replace a project's reference with a new archived package.
On release, set state to `released`. CI compares with the PR base or previous push
and rejects modification, removal or unrelease of an already released version.
An empty version cannot be released. Create `v2` as a separate development entry
and point `latestVersion` to it; retain the complete v1 entry. The latest pointer
is navigation, not an alias that overwrites old reports.

## Generation and failure behavior

Allure **2.46.1** and its distribution checksum live in `tools/allure.json`.
Only that exact generator is accepted. Docker installs Java and the CLI in a
builder stage, then validates/unpacks every package and generates one report per
version/project. The final Nginx stage contains the completed site, not the toolchain.

To assemble outside Docker, install Python requirements and Java 17+:

```bash
python3 scripts/install-allure.py --destination /tmp/livedocs-allure
python3 scripts/assemble.py --output artifacts/site \
  --allure /tmp/livedocs-allure/bin/allure
```

All selected historical versions are included in each image. Assembly uses a
temporary directory and publishes the output only after every package, report and
page succeeds. Existing output directories cannot be overwritten. Missing archives
or failed generation stop publication; the last deployed image stays available.
Changing the renderer is a deliberate code/CI change: frozen manifests preserve
source inputs; the old image digest preserves exact previously rendered files.

LD/4 will adapt Products' Reqnroll output and structured exports to this contract
and open a manifest PR. No service repository changes in LD/2.

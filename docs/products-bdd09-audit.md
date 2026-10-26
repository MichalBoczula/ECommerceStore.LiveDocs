# Products BDD-09 snapshot audit

The development v1 Products report advances from BDD-01 to the completed BDD-09
producer work in [Products PR #208](https://github.com/MichalBoczula/ProductsCatalog/pull/208).
Only the Products reference changes. Users, Orders/Invoices, Payments, retained
versions and the latest-version pointer keep their existing selections.

## Selected producer identity

| Evidence | Value |
| --- | --- |
| Source commit | `ab8fe05e2fee4870c6b1255a8f4d6e5d49d90f5e` |
| Successful master CI | [40394312976](https://github.com/MichalBoczula/ProductsCatalog/actions/runs/40394312976) |
| Generated at | `2026-10-26T20:24:44Z` |
| Bundle SHA-256 | `9625b79583bec33425fd2ca7c1cc43b0a4f323483698614534fbdcf0b25d5da6` |
| Bundle size | 941982 bytes |
| Archive | [Content-addressed Blob](https://stecproductsdevmb261013.blob.core.windows.net/livedocs/reports/products/ab8fe05e2fee4870c6b1255a8f4d6e5d49d90f5e/9625b79583bec33425fd2ca7c1cc43b0a4f323483698614534fbdcf0b25d5da6.zip) (private; build credentials required) |

The selected package is the master archive, not the PR merge-ref bundle. Producer
CI passed 144 acceptance-project tests with no failures/skips. The Allure adapter
emits the 76 BDD cases; the other acceptance-project xUnit checks are separate.

## Reviewed package

- 19 feature files, 60 declarations and 76 expanded BDD cases; 73 stable scenario
  IDs and 76 distinct instance IDs. All previous 64 instance identities survive.
- Every scenario has intent, Given/When/Then, and useful tables/examples or a
  documented technical exception. Source examples match real result identities.
- 140 paired HTTP exchanges, 140 contract observations and 140 source-documentation
  links. Setup, supporting and primary exchanges retain separate roles.
- All 1,026 attachments resolve; JSON-labelled attachments parse. Every one of the
  1,201 manifest entries matches its recorded size and SHA-256.
- The 280 request/response envelopes retain 217 JSON, 50 absent bodies, 11 text,
  one empty body and one malformed JSON body. Raw bytes are represented faithfully.
- All 15 error signatures published by the four active policies appear in actual
  responses, plus the selected-IDs inline guard. Every active rule ID has rejection
  evidence. The 70 primary outcomes link 49 of 50 declared branches.
- Existing bidirectional endpoint/matrix/OpenAPI checks, schema/field examples,
  runtime/source flow and policy comparisons, current/history checks, coverage,
  dependency/secret gates and the image security gate remain required.

## Explicit limits

The remaining branch is `products.branch.list.null-result`: the real Dapper
repository materializes a non-null read-only list and returns an empty collection
as 200. The guard is for a substituted repository violating that contract, so the
audit does not invent a normal list 404 or claim 100% runtime branch coverage.
Hardware rules remain published standalone; money rules remain empty. Rule links
and declared steps are source metadata, not runtime branch telemetry.

These results prove the selected examples and current contract consistency, not
every combination of invalid fields. Controlled pre-save faults do not prove a
real SQL transaction rollback. Historical approval before original implementation
is not established by source-generated documentation. RAG ingestion/indexing and
the equivalent producer cleanups for Users, Invoices and Payments remain separate.

## LiveDocs verification and delivery

The existing production-image smoke check now visits every rendered case in each
selected report, requires the case inventory to match its summary, resolves every
attachment over HTTP and parses JSON-labelled attachments. Regression cases reject
a missing later case, a missing later attachment, malformed advertised JSON and
an incomplete case inventory. Failed source tests remain displayable; host readiness
does not become a test-status gate.

CI validates private archive bytes before Docker, generates Allure with the pinned
CLI, smoke-tests/scans its production image and publishes that same image on main.
The image's `/build-info.json` and the `livedocs-image/image.json` Actions artifact
identify the actual LiveDocs commit/build and immutable deployment digest.

This audit verifies the selected source and built documentation image. Azure
rollout is the existing manual Terraform step and is not claimed executed here.
Update only `app_images.livedocs` in the shared Terraform variables, review a fresh
plan and apply. Then compare `/build-info.json` with the image metadata, and check
`/livedoc/v1/products/bundle.json` selects the source commit above. See the
[container contract](container-contract.md).


"""Synthetic input packages for verification only; never production manifests."""
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from livedocs import package_bundle


def fixture(source, project="products", commit="a" * 40, status="passed"):
    source = Path(source)
    (source / "sources").mkdir(parents=True)
    (source / "bdd").mkdir()
    (source / "allure-results").mkdir()
    repository = "MichalBoczula/ProductsCatalog" if project == "products" else "MichalBoczula/ECommerceStoreUsers"
    metadata = {"schemaVersion": 1, "project": project, "repository": repository, "commitSha": commit,
                "generatedAt": "2026-10-02T20:00:00Z", "workflowRunId": 123}
    values = {
        "openapi.json": {"openapi": "3.0.1", "info": {"title": "CI fixture", "version": "1"},
                         "paths": {f"/{project}": {"get": {"operationId": "FixtureOperation", "responses": {"200": {"description": "OK"}}}}}},
        "flows.json": [{"actionName": "CI fixture flow " + commit[0], "steps": [{"description": "Read fixture records"}]}],
        "validation-policies.json": [{"policyName": "FixturePolicy", "rules": ["Fixture rule"]}],
        "operation-links.json": {"service": project, "operations": [{"operationId": "FixtureOperation", "flow": "FixtureFlow", "policies": ["FixturePolicy"], "scenarios": [{"scenarioId": "CI_FIXTURE_01"}]}]},
    }
    for name, value in values.items():
        (source / "sources" / name).write_text(json.dumps(value), encoding="utf-8")
    (source / "bdd/fixture.feature").write_text("Feature: CI fixture only\n  Scenario: Fixture scenario\n    Given fixture data\n    When fixture action\n    Then fixture result\n", encoding="utf-8")
    identity = str(uuid.uuid5(uuid.NAMESPACE_URL, project + commit))
    attachment = identity + "-attachment.json"
    (source / "allure-results" / attachment).write_text('{"fixture":true}', encoding="utf-8")
    result = {"uuid": identity, "name": "CI fixture only: " + project, "fullName": project + ".fixture",
              "historyId": hashlib.sha256((project + "fixture").encode()).hexdigest(), "status": status,
              "stage": "finished", "start": 1790971200000, "stop": 1790971200100,
              "steps": [{"name": "Fixture step", "status": status, "stage": "finished"}],
              "labels": [{"name": "feature", "value": "CI fixture only"}, {"name": "suite", "value": project}],
              "attachments": [{"name": "Fixture JSON", "source": attachment, "type": "application/json"}]}
    (source / "allure-results" / (identity + "-result.json")).write_text(json.dumps(result), encoding="utf-8")
    return metadata


def reference(source, metadata, cache):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "pending.zip"
    descriptor = package_bundle(source, metadata, archive)
    archive.rename(cache / (descriptor["sha256"] + ".zip"))
    return {key: metadata[key] for key in ["project", "commitSha", "generatedAt", "workflowRunId"]} | {
        "artifact": {"url": "https://cifixtures.blob.core.windows.net/reports/fixture.zip", **descriptor}}


def create(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cache = root / "cache"
    first = root / "products-v1"
    products_v1 = reference(first, fixture(first), cache)
    second = root / "users-v1"
    users_v1 = reference(second, fixture(second, "users", "b" * 40), cache)
    third = root / "products-v2"
    products_v2 = reference(third, fixture(third, commit="c" * 40, status="failed"), cache)
    manifests = root / "manifests"
    manifests.mkdir()
    portal = {"schemaVersion": 1, "latestVersion": "v2", "versions": [
        {"version": "v1", "state": "released", "projects": [products_v1, users_v1]},
        {"version": "v2", "state": "development", "projects": [products_v2]},
    ]}
    (manifests / "portal.json").write_text(json.dumps(portal), encoding="utf-8")
    (manifests / "projects.json").write_text(json.dumps({
        "products": {"name": "Products — CI fixture", "repository": "MichalBoczula/ProductsCatalog"},
        "users": {"name": "Users — CI fixture", "repository": "MichalBoczula/ECommerceStoreUsers"},
    }), encoding="utf-8")
    return manifests, cache


if __name__ == "__main__":
    create(sys.argv[1])

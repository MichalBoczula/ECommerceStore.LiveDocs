"""Producer packaging, private archive IO and reviewable manifest imports."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.parse

from livedocs import (MAX_ARCHIVE, archive_url, materialize, package_bundle, read_json,
                      unpack, validate_bundle, validate_manifests, validate_schema)


def storage(account, container):
    if not re.fullmatch(r"[a-z0-9]{3,24}", account) or container != "livedocs":
        raise ValueError("Use a valid storage account and the dedicated livedocs container")
    return ["--auth-mode", "login", "--account-name", account, "--container-name", container]


def blob_parts(url, account, container):
    archive_url(url)
    parsed = urllib.parse.urlsplit(url)
    prefix = f"/{container}/"
    if parsed.hostname != f"{account}.blob.core.windows.net" or not parsed.path.startswith(prefix):
        raise ValueError("Archive is outside the configured LiveDocs storage boundary")
    name = parsed.path[len(prefix):]
    if not re.fullmatch(r"reports/[a-z][a-z0-9-]*/[0-9a-f]{40}/[0-9a-f]{64}\.zip", name):
        raise ValueError("Archive must use a content-addressed reports path")
    return name


def az(*args):
    return subprocess.run(["az", "storage", "blob", *args], check=True,
                          capture_output=True, text=True).stdout


def download(account, container, name, destination):
    az("download", *storage(account, container), "--name", name, "--file", str(destination),
       "--overwrite", "true", "--output", "none", "--only-show-errors")


def upload_once(file, account, container, name, content_type):
    boundary = storage(account, container)
    exists = json.loads(az("exists", *boundary, "--name", name, "--output", "json"))["exists"]
    if exists:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "existing"
            download(account, container, name, existing)
            if existing.read_bytes() != Path(file).read_bytes():
                raise ValueError("Existing immutable blob contains different bytes")
        return
    # Concurrent conflicts fail safely; a retry verifies the existing bytes.
    az("upload", *boundary, "--name", name, "--file", str(file), "--overwrite", "false",
       "--content-type", content_type, "--output", "none", "--only-show-errors")


def prefetch(reference, cache, account, container):
    name = blob_parts(reference["artifact"]["url"], account, container)
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    artifact = reference["artifact"]
    destination = cache / f"{artifact['sha256']}.zip"
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            pending = Path(directory) / "bundle.zip"
            download(account, container, name, pending)
            if (pending.stat().st_size != artifact["sizeBytes"] or
                    hashlib.sha256(pending.read_bytes()).hexdigest() != artifact["sha256"]):
                raise ValueError("Downloaded archive size/checksum mismatch")
            pending.replace(destination)
    return materialize(reference, cache)


def package_producer(source, exports, results, features, project, repository, commit, run_id, output):
    source, exports, results = Path(source), Path(exports), Path(results)
    with tempfile.TemporaryDirectory() as directory:
        staged = Path(directory)
        for target in ["sources", "bdd", "allure-results"]:
            (staged / target).mkdir()
        for name in ["openapi.json", "flows.json", "validation-policies.json", "operation-links.json"]:
            path = exports / name
            if path.is_symlink():
                raise ValueError("Producer exports cannot be symlinks")
            shutil.copyfile(path, staged / "sources" / name)
        feature_root = source / features
        if not feature_root.resolve().is_relative_to(source.resolve()):
            raise ValueError("Feature root must be inside the producer checkout")
        for path in feature_root.rglob("*.feature"):
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                raise ValueError("Producer features cannot be symlinks")
            destination = staged / "bdd" / path.relative_to(feature_root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        for path in results.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Allure results must be flat files without symlinks")
            shutil.copyfile(path, staged / "allure-results" / path.name)
        metadata = {"schemaVersion": 1, "project": project, "repository": repository,
                    "commitSha": commit, "workflowRunId": run_id,
                    "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        return package_bundle(staged, metadata, output)


def archive_bundle(file, account, container, version, output, repository=None, commit=None, run_id=None):
    storage(account, container)
    if not re.fullmatch(r"v[1-9][0-9]*", version):
        raise ValueError("Invalid documentation version")
    file = Path(file)
    if file.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Bundle exceeds archive size limit")
    with tempfile.TemporaryDirectory() as directory:
        unpack(file, directory)
        metadata = validate_bundle(directory)
    for key, expected in [("repository", repository), ("commitSha", commit), ("workflowRunId", run_id)]:
        if expected is not None and metadata[key] != expected:
            raise ValueError(f"Producer identity mismatch: {key}")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    name = f"reports/{metadata['project']}/{metadata['commitSha']}/{digest}.zip"
    upload_once(file, account, container, name, "application/zip")
    reference = {key: metadata[key] for key in ["project", "commitSha", "generatedAt", "workflowRunId"]}
    reference["artifact"] = {"url": f"https://{account}.blob.core.windows.net/{container}/{name}",
                             "sha256": digest, "sizeBytes": file.stat().st_size}
    receipt = {"schemaVersion": 1, "version": version, "reference": reference}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    candidate = f"candidates/{version}/{metadata['project']}/{metadata['workflowRunId']}-{digest}.json"
    upload_once(output, account, container, candidate, "application/json")
    return receipt


def check_candidate(receipt, version, project, account, container):
    if (not isinstance(receipt, dict) or set(receipt) != {"schemaVersion", "version", "reference"}
            or receipt["schemaVersion"] != 1 or receipt["version"] != version):
        raise ValueError("Invalid candidate receipt")
    reference = receipt["reference"]
    validate_schema({"schemaVersion": 1, "latestVersion": version, "versions": [
        {"version": version, "state": "development", "projects": [reference]}]}, "portal")
    if reference["project"] != project:
        raise ValueError("Candidate project mismatch")
    name = blob_parts(reference["artifact"]["url"], account, container)
    expected = f"reports/{project}/{reference['commitSha']}/{reference['artifact']['sha256']}.zip"
    if name != expected:
        raise ValueError("Candidate path does not match its identity")
    return reference


def verified_run(reference, repository, run, branch="master", workflow=".github/workflows/dotnet.yml"):
    if (run.get("repository", {}).get("full_name") != repository or
            run.get("id") != reference["workflowRunId"] or run.get("head_sha") != reference["commitSha"] or
            run.get("head_branch") != branch or run.get("event") != "push" or run.get("path") != workflow):
        raise ValueError("Candidate does not identify the expected producer CI run")
    return run.get("status") == "completed" and run.get("conclusion") == "success"


def update_manifest(manifests, version, reference):
    portal, projects = validate_manifests(manifests)
    if reference["project"] not in projects:
        raise ValueError("Unregistered producer")
    selected = next((item for item in portal["versions"] if item["version"] == version), None)
    if selected is None or selected["state"] != "development":
        raise ValueError("Import requires an existing development version; released versions are frozen")
    old = next((item for item in selected["projects"] if item["project"] == reference["project"]), None)
    if old == reference:
        return False
    if old and reference["workflowRunId"] <= old["workflowRunId"]:
        raise ValueError("Import cannot roll back or replace a previously selected workflow run")
    selected["projects"] = sorted([item for item in selected["projects"] if item["project"] != reference["project"]]
                                  + [reference], key=lambda item: item["project"])
    destination = Path(manifests) / "portal.json"
    destination.write_text(json.dumps(portal, indent=2) + "\n", encoding="utf-8")
    validate_manifests(manifests)
    return True

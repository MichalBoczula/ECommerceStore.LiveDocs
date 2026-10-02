"""Validate, archive and assemble immutable multi-project documentation snapshots."""
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SOURCES = {"sources/openapi.json", "sources/flows.json",
                    "sources/validation-policies.json", "sources/operation-links.json"}
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_UNPACKED = 500 * 1024 * 1024


def read_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate JSON key: {key}")
            value[key] = item
        return value
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def validate_schema(value, name):
    schema = read_json(ROOT / "schemas" / f"{name}.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def archive_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in {None, 443} or parsed.query or parsed.fragment
            or not re.fullmatch(r"[a-z0-9]{3,24}\.blob\.core\.windows\.net", parsed.hostname)
            or not parsed.path.endswith(".zip")):
        raise ValueError("Use a stable Azure Blob HTTPS ZIP URL without credentials or SAS parameters")
    return url


def validate_manifests(directory, previous=None):
    directory = Path(directory)
    portal = read_json(directory / "portal.json")
    validate_schema(portal, "portal")
    projects = read_json(directory / "projects.json")
    if not isinstance(projects, dict) or not projects:
        raise ValueError("Register projects before publication")
    for slug, project in projects.items():
        if (not re.fullmatch(r"[a-z][a-z0-9-]*", slug) or not isinstance(project, dict)
                or set(project) != {"name", "repository"} or not isinstance(project["name"], str)
                or not project["name"] or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", project["repository"])):
            raise ValueError(f"Invalid project registration: {slug}")
    versions = {}
    for version in portal["versions"]:
        key = version["version"]
        if key in versions:
            raise ValueError(f"Duplicate version: {key}")
        versions[key] = version
        seen = set()
        for reference in version["projects"]:
            slug = reference["project"]
            if slug not in projects or slug in seen:
                raise ValueError(f"Unknown or duplicate project: {slug}")
            seen.add(slug)
            archive_url(reference["artifact"]["url"])
        if version["state"] == "released" and not seen:
            raise ValueError("Cannot release an empty documentation version")
    if portal["latestVersion"] not in versions:
        raise ValueError("latestVersion must reference a published manifest version")
    if previous:
        old = read_json(previous)
        validate_schema(old, "portal")
        for version in old["versions"]:
            if version["state"] == "released" and versions.get(version["version"]) != version:
                raise ValueError(f"Released version is immutable: {version['version']}")
    return portal, projects


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Archive redirects are not allowed")


def materialize(reference, cache):
    artifact = reference["artifact"]
    archive_url(artifact["url"])
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{artifact['sha256']}.zip"
    if not destination.is_file():
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(artifact["url"], timeout=60) as response:
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as download:
                temporary = Path(download.name)
                try:
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > artifact["sizeBytes"] or total > MAX_ARCHIVE:
                            raise ValueError("Archive exceeds declared size")
                        download.write(chunk)
                    download.flush()
                    if total != artifact["sizeBytes"]:
                        raise ValueError("Archive size mismatch")
                    if hashlib.sha256(temporary.read_bytes()).hexdigest() != artifact["sha256"]:
                        raise ValueError("Archive checksum mismatch")
                    temporary.replace(destination)
                finally:
                    temporary.unlink(missing_ok=True)
    if destination.stat().st_size != artifact["sizeBytes"] or hashlib.sha256(destination.read_bytes()).hexdigest() != artifact["sha256"]:
        raise ValueError("Cached archive size/checksum mismatch")
    return destination


def safe_path(name):
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name or str(path) != name.rstrip("/"):
        raise ValueError(f"Unsafe archive path: {name}")
    return path


def unpack(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 10000 or sum(entry.file_size for entry in entries) > MAX_UNPACKED:
            raise ValueError("Archive exceeds extraction limits")
        names = set()
        for entry in entries:
            safe_path(entry.filename)
            if entry.filename in names or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                raise ValueError("Duplicate, linked or encrypted archive entry")
            names.add(entry.filename)
        bundle.extractall(destination)


def walk_attachments(value, root):
    if isinstance(value, dict):
        for attachment in value.get("attachments", []):
            source = attachment.get("source", "")
            safe_path(source)
            if not (root / source).is_file():
                raise ValueError(f"Missing Allure attachment: {source}")
        for item in value.values():
            walk_attachments(item, root)
    elif isinstance(value, list):
        for item in value:
            walk_attachments(item, root)


def validate_bundle(directory, reference=None, registration=None):
    directory = Path(directory)
    metadata = read_json(directory / "bundle.json")
    validate_schema(metadata, "bundle")
    if reference:
        for key in ["project", "commitSha", "generatedAt", "workflowRunId"]:
            if metadata[key] != reference[key]:
                raise ValueError(f"Bundle identity mismatch: {key}")
    if registration and metadata["repository"] != registration["repository"]:
        raise ValueError("Bundle repository does not match project registration")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    if actual != set(metadata["files"]) | {"bundle.json"}:
        raise ValueError("Bundle inventory is incomplete or contains undeclared files")
    for name, expected in metadata["files"].items():
        safe_path(name)
        if not name.startswith(("sources/", "allure-results/", "bdd/")):
            raise ValueError(f"Unexpected bundle content: {name}")
        path = directory / name
        if path.is_symlink() or path.stat().st_size != expected["sizeBytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError(f"Bundle file size/checksum mismatch: {name}")
    if not REQUIRED_SOURCES <= actual or not any(name.startswith("bdd/") and name.endswith(".feature") for name in actual):
        raise ValueError("Missing OpenAPI, flows, validation policies, operation links or BDD sources")
    for name in REQUIRED_SOURCES:
        data = read_json(directory / name)
        if not isinstance(data, (dict, list)):
            raise ValueError(f"Expected structured source: {name}")
    api = read_json(directory / "sources/openapi.json")
    if not isinstance(api, dict) or not str(api.get("openapi", "")).startswith("3.") or not isinstance(api.get("paths"), dict):
        raise ValueError("Invalid OpenAPI source")
    results = list((directory / "allure-results").glob("*-result.json"))
    if not results:
        raise ValueError("No Allure test results")
    for result in results:
        data = read_json(result)
        if not data.get("uuid") or not data.get("name") or data.get("status") not in {"passed", "failed", "broken", "skipped", "unknown"}:
            raise ValueError("Incomplete Allure test result")
        walk_attachments(data, directory / "allure-results")
    for container in (directory / "allure-results").glob("*-container.json"):
        walk_attachments(read_json(container), directory / "allure-results")
    return metadata


def package_bundle(source, metadata, output):
    source, output = Path(source), Path(output)
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Package output must be outside the source directory")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("Bundle sources must not contain symlinks")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as staging:
        staging = Path(staging)
        shutil.copytree(source, staging, dirs_exist_ok=True)
        files = {}
        for path in sorted(staging.rglob("*")):
            if path.is_symlink():
                raise ValueError("Bundle sources must not contain symlinks")
            if path.is_file() and path.name != "bundle.json":
                files[path.relative_to(staging).as_posix()] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "sizeBytes": path.stat().st_size}
        metadata = dict(metadata, files=files)
        (staging / "bundle.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        validate_bundle(staging)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(path.relative_to(staging).as_posix(), (1980, 1, 1, 0, 0, 0))
                    archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    if output.stat().st_size > MAX_ARCHIVE:
        output.unlink()
        raise ValueError("Bundle exceeds archive size limit")
    return {"sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "sizeBytes": output.stat().st_size}


def page(title, body, home="/livedoc/"):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)} · ECommerceStore LiveDocs</title>
<link rel="stylesheet" href="/livedoc/styles.css"></head><body><main>
<nav><a href="{home}">LiveDocs</a></nav><h1>{html.escape(title)}</h1>{body}</main></body></html>'''


def write_page(path, title, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(title, body), encoding="utf-8")


def render_project(target, bundle, reference, registration, version):
    name = registration["name"]
    sha = reference["commitSha"]
    repo = registration["repository"]
    body = f'''<p><a href="../">{version['version']}</a> · {html.escape(version['state'])}</p>
<p>Source commit: <a href="https://github.com/{repo}/commit/{sha}">{sha}</a><br>
Generated: {html.escape(reference['generatedAt'])}<br>
<a href="https://github.com/{repo}/actions/runs/{reference['workflowRunId']}">Source CI run</a></p>
<section><h2>BDD test report</h2><p><a href="allure/">Open Allure report</a></p></section>
<section><h2>API contract</h2><p><a href="openapi.json">Download OpenAPI</a></p><table><thead><tr><th>Method</th><th>Path</th><th>Operation</th></tr></thead><tbody>'''
    api = read_json(bundle / "sources/openapi.json")
    for route, operations in api["paths"].items():
        for method, operation in operations.items():
            if method.lower() in {"get", "post", "put", "delete", "patch", "head", "options", "trace"}:
                body += f"<tr><td>{method.upper()}</td><td>{html.escape(route)}</td><td>{html.escape(operation.get('summary') or operation.get('operationId', ''))}</td></tr>"
    body += "</tbody></table></section>"
    for title, filename in [("Business flows", "flows.json"), ("Validation rules", "validation-policies.json"), ("Operation and scenario links", "operation-links.json")]:
        data = read_json(bundle / "sources" / filename)
        body += f'<section><h2>{title}</h2><p><a href="{filename}">Download JSON</a></p><pre>{html.escape(json.dumps(data, indent=2, ensure_ascii=False))}</pre></section>'
    body += '<section><h2>BDD scenarios</h2>'
    for feature in sorted((bundle / "bdd").rglob("*.feature")):
        label = feature.relative_to(bundle / "bdd").as_posix()
        body += f'<details><summary>{html.escape(label)}</summary><pre>{html.escape(feature.read_text(encoding="utf-8-sig"))}</pre></details>'
    body += '</section><p><a href="bundle.json">Artifact metadata and file checksums</a></p>'
    write_page(target / "index.html", name, body)


def assemble(manifests, cache, output, allure="allure", previous=None):
    portal, projects = validate_manifests(manifests, previous)
    output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    config = read_json(ROOT / "tools/allure.json")
    # A directory appears only after all artifacts and reports have succeeded.
    if output.exists():
        raise ValueError("Output already exists; assemble into a new directory to preserve the last good snapshot")
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        staging = Path(staging)
        site = staging / "site"
        shutil.copytree(ROOT / "site", site)
        catalog = dict(portal, allureVersion=config["version"])
        (site / "livedoc/catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        for version in portal["versions"]:
            slug = version["version"]
            directory = site / "livedoc" / slug
            cards = []
            for reference in version["projects"]:
                project = reference["project"]
                archive = materialize(reference, cache)
                bundle = staging / "bundles" / slug / project
                unpack(archive, bundle)
                metadata = validate_bundle(bundle, reference, projects[project])
                target = directory / project
                target.mkdir(parents=True)
                actual_version = subprocess.check_output([allure, "--version"], text=True).strip()
                if actual_version != config["version"]:
                    raise ValueError(f"Expected Allure {config['version']}, found {actual_version}")
                subprocess.run([allure, "generate", str(bundle / "allure-results"), "--output", str(target / "allure"), "--clean"], check=True)
                if not (target / "allure/index.html").is_file() or not (target / "allure/widgets/summary.json").is_file():
                    raise ValueError("Allure generation produced an incomplete report")
                summary = read_json(target / "allure/widgets/summary.json")
                cases = [read_json(path) for path in (bundle / "allure-results").glob("*-result.json")]
                expected_cases = len({case.get("historyId") or case["uuid"] for case in cases})
                if summary.get("statistic", {}).get("total") != expected_cases:
                    raise ValueError("Allure report lost test results")
                for source in REQUIRED_SOURCES:
                    shutil.copy2(bundle / source, target / Path(source).name)
                shutil.copy2(bundle / "bundle.json", target / "bundle.json")
                shutil.copytree(bundle / "bdd", target / "bdd")
                shutil.copytree(bundle / "allure-results", target / "allure-results")
                render_project(target, bundle, reference, projects[project], version)
                cards.append(f'<li><a href="{project}/">{html.escape(projects[project]["name"])}</a> · <code>{metadata["commitSha"][:12]}</code></li>')
            body = f'<p>{html.escape(version["state"])} documentation snapshot</p><ul>{"".join(cards)}</ul>'
            if not cards:
                body += '<p>No service reports have been published for this version yet.</p>'
            write_page(directory / "index.html", slug, body)
        links = ''.join(f'<li><a href="{item["version"]}/">{item["version"]}</a> · {item["state"]}</li>' for item in portal["versions"])
        body = f'<p>Executable documentation for the ECommerceStore services.</p><p><a href="{portal["latestVersion"]}/">Open latest version ({portal["latestVersion"]})</a></p><h2>Versions</h2><ul>{links}</ul>'
        write_page(site / "livedoc/index.html", "ECommerceStore LiveDocs", body)
        # Convenience redirect is relative; versioned routes always remain present.
        latest = portal["latestVersion"]
        (site / "livedoc/latest").mkdir()
        (site / "livedoc/latest/index.html").write_text(f'<!doctype html><meta http-equiv="refresh" content="0;url=../{latest}/"><a href="../{latest}/">{latest}</a>', encoding="utf-8")
        site.rename(output)
    return catalog

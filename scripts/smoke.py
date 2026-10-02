#!/usr/bin/env python3
"""Check real HTTP responses, redirects, missing assets and snapshot identity."""
import argparse
from html.parser import HTMLParser
import json
import time
import urllib.error
import urllib.request
import urllib.parse


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        source = attributes.get("src") if tag == "script" else attributes.get("href") if tag == "link" else None
        if source and not urllib.parse.urlsplit(source).scheme and not source.startswith("//"):
            self.paths.append(source)


def json_response(base_url, path):
    actual, headers, body = request(base_url, path)
    assert actual == 200 and "application/json" in headers.get("Content-Type", ""), f"Missing JSON: {path}"
    return json.loads(body)


def first_case(tree):
    if "status" in tree:
        return tree["uid"]
    for child in tree.get("children", []):
        result = first_case(child)
        if result:
            return result


def attachments(value):
    if isinstance(value, dict):
        yield from value.get("attachments", [])
        for child in value.values():
            yield from attachments(child)
    elif isinstance(value, list):
        for child in value:
            yield from attachments(child)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(base_url, path):
    opener = urllib.request.build_opener(NoRedirect)
    try:
        response = opener.open(base_url.rstrip("/") + path, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.code, response.headers, response.read()


def check(base_url, expected_sha=None):
    for path, status, target in [("/", 302, "/livedoc/"), ("/livedoc", 301, "/livedoc/")]:
        actual, headers, _ = request(base_url, path)
        assert actual == status, f"{path}: expected {status}, got {actual}"
        # Nginx may emit an absolute redirect URL.
        assert headers["Location"].endswith(target), f"{path}: incorrect redirect"
    for path in ["/health/live", "/health/ready"]:
        actual, headers, body = request(base_url, path)
        assert actual == 200, f"{path}: expected 200, got {actual}"
        assert "application/json" in headers.get("Content-Type", ""), path
        assert json.loads(body)["status"] in {"healthy", "ready"}, path
    actual, headers, body = request(base_url, "/livedoc/")
    assert actual == 200 and b"ECommerceStore LiveDocs" in body, "Portal is missing"
    assert "text/html" in headers.get("Content-Type", ""), "Portal media type"
    assert headers.get("X-Content-Type-Options") == "nosniff", "Missing security header"
    actual, headers, body = request(base_url, "/livedoc/styles.css")
    assert actual == 200 and "text/css" in headers.get("Content-Type", "") and body, "Missing CSS"
    catalog = json_response(base_url, "/livedoc/catalog.json")
    for version in catalog["versions"]:
        prefix = f"/livedoc/{version['version']}/"
        actual, _, _ = request(base_url, prefix)
        assert actual == 200, f"Missing version page: {prefix}"
        for project in version["projects"]:
            path = prefix + project["project"] + "/"
            actual, _, body = request(base_url, path)
            assert actual == 200 and project["commitSha"].encode() in body, f"Missing project provenance: {path}"
            for name in ["openapi.json", "flows.json", "validation-policies.json", "operation-links.json"]:
                json_response(base_url, path + name)
            metadata = json_response(base_url, path + "bundle.json")
            assert metadata["commitSha"] == project["commitSha"], f"Wrong bundle identity: {path}"
            feature = next(name for name in metadata["files"] if name.startswith("bdd/") and name.endswith(".feature"))
            actual, _, body = request(base_url, path + feature)
            assert actual == 200 and body, f"Missing BDD source: {path}"
            actual, _, body = request(base_url, path + "allure/")
            assert actual == 200 and b"Allure Report" in body, f"Missing Allure: {path}"
            assets = Assets()
            assets.feed(body.decode("utf-8"))
            assert assets.paths, f"Missing Allure assets: {path}"
            for asset in assets.paths:
                url = urllib.parse.urljoin(path + "allure/", asset)
                actual, _, content = request(base_url, url)
                assert actual == 200 and content, f"Missing Allure asset: {url}"
            summary = json_response(base_url, path + "allure/widgets/summary.json")
            assert summary["statistic"]["total"] > 0, f"Empty report: {path}"
            case_id = first_case(json_response(base_url, path + "allure/data/suites.json"))
            assert case_id, f"Missing generated test case: {path}"
            case = json_response(base_url, path + f"allure/data/test-cases/{case_id}.json")
            for attachment in attachments(case):
                url = path + "allure/data/attachments/" + attachment["source"]
                actual, _, content = request(base_url, url)
                assert actual == 200 and len(content) == attachment["size"], f"Missing/truncated report attachment: {url}"
            for suffix in ["missing.js", "allure/data/missing.json"]:
                actual, _, _ = request(base_url, path + suffix)
                assert actual == 404, f"Missing report asset returned {actual}: {path + suffix}"
    for path in ["/missing", "/livedoc/missing", "/livedoc/missing.js", "/ready.json"]:
        actual, _, _ = request(base_url, path)
        assert actual == 404, f"{path}: missing content must return 404, got {actual}"
    actual, _, body = request(base_url, "/build-info.json")
    assert actual == 200, "Missing deployment identity"
    identity = json.loads(body)
    assert identity["commitSha"] and identity["builtAt"], "Incomplete deployment identity"
    if expected_sha:
        assert identity["commitSha"] == expected_sha, "Public endpoint serves a different commit"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--expected-sha")
    parser.add_argument("--attempts", type=int, default=30)
    args = parser.parse_args()
    for attempt in range(args.attempts):
        try:
            check(args.base_url, args.expected_sha)
            print(f"LiveDocs smoke checks passed: {args.base_url}")
            return
        except (AssertionError, OSError, ValueError, KeyError) as error:
            if attempt + 1 == args.attempts:
                raise SystemExit(f"LiveDocs smoke check failed: {error}") from error
            time.sleep(2)


if __name__ == "__main__":
    main()

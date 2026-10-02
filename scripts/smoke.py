#!/usr/bin/env python3
"""Check real HTTP responses, redirects, missing assets and snapshot identity."""
import argparse
import json
import time
import urllib.error
import urllib.request


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

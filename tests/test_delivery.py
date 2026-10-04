"""Delivery regression tests; HTTP hosting is checked against Nginx in CI."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load("smoke", "scripts/smoke.py")


class SmokeTests(unittest.TestCase):
    @staticmethod
    def response(base, path):
        if path in {"/", "/livedoc"}:
            return (302 if path == "/" else 301), {"Location": "/livedoc/"}, b""
        if path.startswith("/health/"):
            return 200, {"Content-Type": "application/json"}, b'{"status":"ready"}'
        if path == "/livedoc/":
            return 200, {"Content-Type": "text/html", "X-Content-Type-Options": "nosniff"}, b"ECommerceStore LiveDocs"
        if path == "/livedoc/styles.css":
            return 200, {"Content-Type": "text/css"}, b"body {}"
        if path == "/livedoc/catalog.json":
            return 200, {"Content-Type": "application/json"}, b'{"versions":[]}'
        if path == "/build-info.json":
            return 200, {}, json.dumps({"commitSha": "a" * 40, "builtAt": "now"}).encode()
        return 404, {}, b""

    def test_wrong_image_commit_is_rejected(self):
        with patch.object(smoke, "request", side_effect=self.response):
            with self.assertRaisesRegex(AssertionError, "different commit"):
                smoke.check("http://host", "b" * 40)

    def test_spa_fallback_cannot_hide_missing_report_assets(self):
        def fallback(base, path):
            if path == "/livedoc/missing.js":
                return 200, {"Content-Type": "text/html"}, b"portal"
            return self.response(base, path)
        with patch.object(smoke, "request", side_effect=fallback):
            with self.assertRaisesRegex(AssertionError, "missing content must return 404"):
                smoke.check("http://host", "a" * 40)


if __name__ == "__main__":
    unittest.main()

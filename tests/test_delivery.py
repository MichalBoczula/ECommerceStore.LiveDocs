"""Delivery regression tests; HTTP hosting is checked against Nginx in CI."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aca = load("aca", "scripts/render-aca.py")
smoke = load("smoke", "scripts/smoke.py")
IMAGE = "mb0101/ecommerce-store-livedocs@sha256:" + "a" * 64
ENVIRONMENT = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.App/managedEnvironments/env"


class DeploymentTests(unittest.TestCase):
    def test_mutable_and_unrelated_images_are_rejected(self):
        for image in ["mb0101/ecommerce-store-livedocs:latest", "other/repo@sha256:" + "a" * 64,
                      IMAGE[:-1], IMAGE + ":latest"]:
            with self.subTest(image=image), self.assertRaises(ValueError):
                aca.render(image, ENVIRONMENT, "polandcentral", "ld-123")

    def test_http_scale_to_zero_and_probes_have_matching_ports(self):
        app = aca.render(IMAGE, ENVIRONMENT, "polandcentral", "ld-123")
        props = app["properties"]
        self.assertEqual(props["template"]["scale"]["minReplicas"], 0)
        self.assertIn("http", props["template"]["scale"]["rules"][0])
        port = props["configuration"]["ingress"]["targetPort"]
        probes = props["template"]["containers"][0]["probes"]
        self.assertEqual({probe["type"] for probe in probes}, {"Startup", "Readiness", "Liveness"})
        self.assertTrue(all(probe["httpGet"]["port"] == port for probe in probes))
        self.assertFalse(props["configuration"]["ingress"]["allowInsecure"])

    def test_missing_environment_and_bad_revision_are_rejected(self):
        for environment, revision in [("", "ld-123"), (ENVIRONMENT, "ld--123"),
                                      (ENVIRONMENT, "ld-"), (ENVIRONMENT, "A")]:
            with self.subTest(environment=environment, revision=revision), self.assertRaises(ValueError):
                aca.render(IMAGE, environment, "polandcentral", revision)

    def test_missing_configuration_fails_before_azure_is_called(self):
        result = subprocess.run(["bash", "scripts/deploy-azure.sh", IMAGE, "a" * 40],
                                cwd=ROOT, env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AZURE_RESOURCE_GROUP", result.stderr)


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

    def test_wrong_deployed_commit_is_rejected(self):
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

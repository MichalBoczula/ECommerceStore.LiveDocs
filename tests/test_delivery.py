"""Delivery regression tests; HTTP hosting is checked against Nginx in CI."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load("smoke", "scripts/smoke.py")
gate = load("gate", "scripts/check-quality-gate.py")


class PipelineTests(unittest.TestCase):
    def jobs(self, event):
        results = {name: {"result": "success"} for name in gate.REQUIRED}
        results["dependency-review"] = {"result": "success" if event == "pull_request" else "skipped"}
        return results

    def test_all_checks_are_required_on_pr_push_and_manual_runs(self):
        for event in ["pull_request", "push", "workflow_dispatch"]:
            gate.require_jobs(self.jobs(event), event)
        for name in gate.REQUIRED:
            for result in ["failure", "cancelled", "skipped", None]:
                jobs = self.jobs("pull_request")
                jobs[name] = {"result": result}
                with self.subTest(name=name, result=result), self.assertRaises(ValueError):
                    gate.require_jobs(jobs, "pull_request")
        jobs = self.jobs("push")
        del jobs["secret-scan"]
        with self.assertRaises(ValueError):
            gate.require_jobs(jobs, "push")

    def test_pr_dependency_review_cannot_be_skipped(self):
        jobs = self.jobs("pull_request")
        jobs["dependency-review"]["result"] = "skipped"
        with self.assertRaisesRegex(ValueError, "Dependency Review"):
            gate.require_jobs(jobs, "pull_request")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            gate.require_jobs(self.jobs("push"), "pull_request_target")

    def test_publication_requires_main_and_refuses_pull_requests(self):
        for ref, event in [("refs/heads/feature", "push"), ("refs/heads/main", "pull_request")]:
            with tempfile.TemporaryDirectory() as temporary:
                fake = Path(temporary) / "docker"
                marker = Path(temporary) / "called"
                fake.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
                fake.chmod(0o755)
                env = dict(os.environ, PATH=temporary + os.pathsep + os.environ["PATH"],
                           GITHUB_REF=ref, GITHUB_EVENT_NAME=event)
                result = subprocess.run(["bash", "scripts/ci.sh", "publish"], cwd=ROOT,
                                        env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists(), "Untrusted publication must stop before Docker")

    def test_publication_uses_matching_digest_and_rejects_registry_mismatch(self):
        for mismatched in [False, True]:
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                fake = directory / "docker"
                fake.write_text('''#!/usr/bin/env python3
import os, sys
if sys.argv[1:3] == ["image", "inspect"]:
    print("sha256:" + "c" * 64)
elif sys.argv[1] == "push":
    digest = "b" if os.environ["MISMATCH"] == "True" and sys.argv[2].endswith(":latest") else "a"
    print("latest: digest: sha256:" + digest * 64 + " size: 123")
''')
                fake.chmod(0o755)
                env = dict(os.environ, PATH=temporary + os.pathsep + os.environ["PATH"],
                           GITHUB_REF="refs/heads/main", GITHUB_EVENT_NAME="push", GITHUB_SHA="d" * 40,
                           RUNNER_TEMP=temporary, GITHUB_OUTPUT=str(directory / "output"),
                           GITHUB_STEP_SUMMARY=str(directory / "summary"), BUILD_DATE="2026-10-05T00:00:00Z",
                           VERIFY_RESULTS_DIR=str(directory / "results"), MISMATCH=str(mismatched))
                result = subprocess.run(["bash", "scripts/ci.sh", "publish"], cwd=ROOT,
                                        env=env, capture_output=True, text=True)
                metadata = directory / "results/image.json"
                with self.subTest(mismatched=mismatched):
                    if mismatched:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertFalse(metadata.exists())
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(json.loads(metadata.read_text())["image"],
                                         "mb0101/ecommerce-store-livedocs@sha256:" + "a" * 64)
                        self.assertEqual(json.loads(metadata.read_text())["commitSha"], "d" * 40)


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

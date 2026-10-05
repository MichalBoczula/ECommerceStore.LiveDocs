"""Regression checks for producer provenance, immutable blobs and manifest imports."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bundle_fixtures import fixture, reference
import delivery
from livedocs import read_json, unpack, validate_bundle


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.metadata = fixture(self.source)
        self.cache = self.root / "cache"
        self.reference = reference(self.source, self.metadata, self.cache)
        self.reference["artifact"]["url"] = (
            f"https://testarchive.blob.core.windows.net/livedocs/reports/products/"
            f"{self.reference['commitSha']}/{self.reference['artifact']['sha256']}.zip")
        self.receipt = {"schemaVersion": 1, "version": "v1", "reference": self.reference}
        self.manifests = self.root / "manifests"
        self.manifests.mkdir()
        (self.manifests / "projects.json").write_text(json.dumps({
            "products": {"name": "Products", "repository": "MichalBoczula/ProductsCatalog"}}))
        self.write_portal()

    def write_portal(self, state="development", projects=None):
        (self.manifests / "portal.json").write_text(json.dumps({
            "schemaVersion": 1, "latestVersion": "v1", "versions": [
                {"version": "v1", "state": state, "projects": projects or []}]}))

    def test_producer_packages_only_features_and_all_required_inputs(self):
        (self.source / "bdd/fixture.feature.cs").write_text("excluded generated code")
        output = self.root / "producer.zip"
        delivery.package_producer(self.source, self.source / "sources", self.source / "allure-results",
                                  "bdd", "products", self.metadata["repository"], "a" * 40, 123, output)
        staged = self.root / "unpacked"
        unpack(output, staged)
        metadata = validate_bundle(staged)
        self.assertEqual(metadata["workflowRunId"], 123)
        self.assertIn("bdd/fixture.feature", metadata["files"])
        self.assertNotIn("bdd/fixture.feature.cs", metadata["files"])

    def test_producer_rejects_missing_export_nested_results_and_symlinks(self):
        kwargs = dict(source=self.source, exports=self.source / "sources", results=self.source / "allure-results",
                      features="bdd", project="products", repository=self.metadata["repository"],
                      commit="a" * 40, run_id=123, output=self.root / "producer.zip")
        (self.source / "allure-results/nested").mkdir()
        with self.assertRaisesRegex(ValueError, "flat"):
            delivery.package_producer(**kwargs)
        (self.source / "allure-results/nested").rmdir()
        (self.source / "bdd/link.feature").symlink_to(self.source / "bdd/fixture.feature")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            delivery.package_producer(**kwargs)
        (self.source / "bdd/link.feature").unlink()
        (self.source / "sources/flows.json").unlink()
        with self.assertRaises(FileNotFoundError):
            delivery.package_producer(**kwargs)

    def test_archive_identity_and_blob_path_are_checked_before_upload(self):
        archive = self.cache / (self.reference["artifact"]["sha256"] + ".zip")
        with patch.object(delivery, "upload_once") as upload:
            with self.assertRaisesRegex(ValueError, "repository"):
                delivery.archive_bundle(archive, "testarchive", "livedocs", "v1", self.root / "receipt.json",
                                        repository="Wrong/Repository")
            upload.assert_not_called()
            receipt = delivery.archive_bundle(archive, "testarchive", "livedocs", "v1",
                                               self.root / "receipt.json", repository=self.metadata["repository"])
            self.assertEqual(receipt, self.receipt)
            self.assertEqual(upload.call_count, 2)
            self.assertTrue(upload.call_args_list[0].args[3].startswith("reports/products/"))
            self.assertTrue(upload.call_args_list[1].args[3].startswith("candidates/v1/products/"))

    def test_archive_retry_verifies_existing_bytes_and_never_overwrites(self):
        file = self.root / "input"
        file.write_bytes(b"original")
        def download(account, container, name, destination):
            destination.write_bytes(b"original")
        with patch.object(delivery, "az", return_value='{"exists":true}') as azure, \
                patch.object(delivery, "download", side_effect=download):
            delivery.upload_once(file, "testarchive", "livedocs", "reports/example", "application/zip")
            self.assertEqual(azure.call_count, 1)
            file.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "different bytes"):
                delivery.upload_once(file, "testarchive", "livedocs", "reports/example", "application/zip")
        with patch.object(delivery, "az", return_value='{"exists":false}') as azure:
            delivery.upload_once(file, "testarchive", "livedocs", "reports/example", "application/zip")
            args = azure.call_args.args
            self.assertEqual(args[args.index("--overwrite") + 1], "false")

    def test_prefetch_bounds_storage_and_detects_corrupted_downloads_and_cache(self):
        empty = self.root / "empty-cache"
        with patch.object(delivery, "download", side_effect=lambda a, c, n, p: p.write_bytes(b"corrupt")):
            with self.assertRaisesRegex(ValueError, "checksum"):
                delivery.prefetch(self.reference, empty, "testarchive", "livedocs")
        self.assertEqual(list(empty.iterdir()), [])
        destination = self.cache / (self.reference["artifact"]["sha256"] + ".zip")
        destination.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "Cached"):
            delivery.prefetch(self.reference, self.cache, "testarchive", "livedocs")
        with patch.object(delivery, "download") as download:
            with self.assertRaisesRegex(ValueError, "boundary"):
                delivery.prefetch(self.reference, empty, "anotheraccount", "livedocs")
            download.assert_not_called()
        with self.assertRaisesRegex(ValueError, "dedicated"):
            delivery.storage("testarchive", "photos")

    def test_candidate_rejects_other_versions_projects_accounts_and_paths(self):
        self.assertEqual(delivery.check_candidate(self.receipt, "v1", "products", "testarchive", "livedocs"),
                         self.reference)
        for change in ["version", "project", "account", "path", "digest"]:
            receipt = copy.deepcopy(self.receipt)
            if change == "version": receipt["version"] = "v2"
            if change == "project": receipt["reference"]["project"] = "users"
            if change == "account": receipt["reference"]["artifact"]["url"] = self.reference["artifact"]["url"].replace("testarchive", "otherarchive")
            if change == "path": receipt["reference"]["artifact"]["url"] = self.reference["artifact"]["url"].replace("reports/products/", "reports/users/")
            if change == "digest": receipt["reference"]["artifact"]["sha256"] = "f" * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                delivery.check_candidate(receipt, "v1", "products", "testarchive", "livedocs")

    def test_import_requires_successful_matching_producer_run(self):
        run = {"repository": {"full_name": self.metadata["repository"]}, "id": self.metadata["workflowRunId"],
               "head_sha": "a" * 40, "head_branch": "master", "event": "push",
               "path": ".github/workflows/dotnet.yml", "status": "completed", "conclusion": "success"}
        self.assertTrue(delivery.verified_run(self.reference, self.metadata["repository"], run))
        for conclusion in ["failure", "cancelled", "skipped", None]:
            self.assertFalse(delivery.verified_run(self.reference, self.metadata["repository"], dict(run, conclusion=conclusion)))
        self.assertFalse(delivery.verified_run(self.reference, self.metadata["repository"], dict(run, status="in_progress")))
        for key, value in [("id", 999), ("head_sha", "b" * 40), ("head_branch", "feature"),
                           ("event", "pull_request"), ("path", ".github/workflows/other.yml")]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "expected producer"):
                delivery.verified_run(self.reference, self.metadata["repository"], dict(run, **{key: value}))

    def test_import_is_idempotent_and_preserves_released_versions(self):
        self.assertTrue(delivery.update_manifest(self.manifests, "v1", self.reference))
        self.assertFalse(delivery.update_manifest(self.manifests, "v1", self.reference))
        changed = copy.deepcopy(self.reference)
        changed["commitSha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "roll back"):
            delivery.update_manifest(self.manifests, "v1", changed)
        changed["workflowRunId"] += 1
        self.assertTrue(delivery.update_manifest(self.manifests, "v1", changed))
        self.write_portal("released", [changed])
        before = (self.manifests / "portal.json").read_bytes()
        for version in ["v1", "v2"]:
            with self.assertRaisesRegex(ValueError, "development"):
                delivery.update_manifest(self.manifests, version, self.reference)
        self.assertEqual(before, (self.manifests / "portal.json").read_bytes())

    def test_discovery_cli_checks_finished_run_before_updating_manifest(self):
        spec = importlib.util.spec_from_file_location("import_bundle", ROOT / "scripts/import-bundle.py")
        importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(importer)
        digest = self.reference["artifact"]["sha256"]
        run_id = self.reference["workflowRunId"]
        name = f"candidates/v1/products/{run_id}-{digest}.json"
        run = {"repository": {"full_name": self.metadata["repository"]}, "id": run_id,
               "head_sha": "a" * 40, "head_branch": "master", "event": "push",
               "path": ".github/workflows/dotnet.yml", "status": "in_progress", "conclusion": None}
        def download(account, container, blob, destination):
            destination.write_text(json.dumps(self.receipt))
        argv = ["import-bundle.py", "--account", "testarchive", "--manifests", str(self.manifests),
                "--cache", str(self.cache)]
        with patch.object(sys, "argv", argv), patch.object(importer, "az", return_value=json.dumps([name])), \
                patch.object(importer, "download", side_effect=download), \
                patch.object(importer.subprocess, "run") as github:
            github.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(run))
            importer.main()
            self.assertEqual(read_json(self.manifests / "portal.json")["versions"][0]["projects"], [])
            run.update(status="completed", conclusion="success")
            github.return_value.stdout = json.dumps(run)
            importer.main()
            self.assertEqual(read_json(self.manifests / "portal.json")["versions"][0]["projects"], [self.reference])
            calls = github.call_count
            importer.main()
            self.assertEqual(github.call_count, calls, "Already selected runs do not need another API call")

    def test_discovery_rejects_ambiguous_rerun_receipts(self):
        spec = importlib.util.spec_from_file_location("import_bundle", ROOT / "scripts/import-bundle.py")
        importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(importer)
        names = [f"candidates/v1/products/123-{digest}.json" for digest in ["a" * 64, "b" * 64]]
        with patch.object(sys, "argv", ["import-bundle.py", "--account", "testarchive", "--manifests", str(self.manifests)]), \
                patch.object(importer, "az", return_value=json.dumps(names)), \
                patch.object(importer, "download") as download:
            with self.assertRaisesRegex(ValueError, "Ambiguous"):
                importer.main()
            download.assert_not_called()


if __name__ == "__main__":
    unittest.main()

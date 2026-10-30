import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import MagicMock, patch

from jsonschema import ValidationError

from bundle_fixtures import create, fixture, reference
from livedocs import MAX_ARCHIVE, MAX_BUNDLE_FILES, MAX_UNPACKED, validate_schema, archive_url, assemble, materialize, package_bundle, read_json, unpack, validate_bundle, validate_manifests


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifests, self.cache = create(self.root / "fixtures")
        self.portal = read_json(self.manifests / "portal.json")
        self.reference = self.portal["versions"][0]["projects"][0]

    def rewrite(self, portal):
        (self.manifests / "portal.json").write_text(json.dumps(portal))

    def test_unknown_duplicate_project_and_latest_are_rejected(self):
        for kind in ["unknown", "duplicate", "latest"]:
            portal = copy.deepcopy(self.portal)
            if kind == "unknown":
                portal["versions"][0]["projects"][0]["project"] = "unregistered"
            elif kind == "duplicate":
                portal["versions"][0]["projects"].append(portal["versions"][0]["projects"][0])
            else:
                portal["latestVersion"] = "v3"
            self.rewrite(portal)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_manifests(self.manifests)

    def test_released_version_cannot_change_or_be_removed(self):
        previous = self.root / "previous.json"
        previous.write_text(json.dumps(self.portal))
        for kind in ["change", "remove", "unrelease"]:
            portal = copy.deepcopy(self.portal)
            if kind == "change":
                portal["versions"][0]["projects"][0]["commitSha"] = "d" * 40
            elif kind == "remove":
                portal["versions"].pop(0)
            else:
                portal["versions"][0]["state"] = "development"
            self.rewrite(portal)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "immutable"):
                validate_manifests(self.manifests, previous)

    def test_development_version_can_advance_without_changing_release(self):
        previous = self.root / "previous.json"
        previous.write_text(json.dumps(self.portal))
        self.portal["versions"][1]["projects"][0]["commitSha"] = "d" * 40
        self.rewrite(self.portal)
        validate_manifests(self.manifests, previous)

    def test_archive_tampering_is_rejected_even_from_cache(self):
        archive = self.cache / (self.reference["artifact"]["sha256"] + ".zip")
        data = bytearray(archive.read_bytes())
        data[len(data) // 2] ^= 1
        archive.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "checksum"):
            materialize(self.reference, self.cache)

    def test_zip_escape_and_duplicate_entries_are_rejected(self):
        for name in ["../escape", "/escape", "a\\escape"]:
            archive = self.root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as value:
                value.writestr(name, "bad")
            with self.subTest(name=name), self.assertRaises(ValueError):
                unpack(archive, self.root / "extracted")
        self.assertFalse((self.root / "escape").exists())
        archive = self.root / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive, "w") as value:
                value.writestr("bundle.json", "first")
                value.writestr("bundle.json", "second")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            unpack(archive, self.root / "duplicate-extracted")

    def test_packaging_rejects_symlinks_before_copying_sources(self):
        source = self.root / "source"
        metadata = fixture(source)
        (source / "sources/linked.json").symlink_to(source / "sources/flows.json")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            package_bundle(source, metadata, self.root / "linked.zip")

    def test_bundle_identity_and_file_integrity_are_required(self):
        bundle = self.root / "unpacked"
        unpack(materialize(self.reference, self.cache), bundle)
        bad = dict(self.reference, commitSha="d" * 40)
        with self.assertRaisesRegex(ValueError, "identity"):
            validate_bundle(bundle, bad)
        (bundle / "sources/flows.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_bundle(bundle, self.reference)

    def test_missing_allure_attachment_is_rejected(self):
        source = self.root / "source"
        metadata = fixture(source)
        next((source / "allure-results").glob("*-attachment.json")).unlink()
        with self.assertRaisesRegex(ValueError, "attachment"):
            package_bundle(source, metadata, self.root / "missing.zip")

    def test_large_evidence_bundle_round_trips_above_the_former_file_limit(self):
        source = self.root / "large-source"
        metadata = fixture(source)
        result_path = next((source / "allure-results").glob("*-result.json"))
        result = read_json(result_path)
        for index in range(10_001):
            name = f"evidence-{index:05d}-attachment.json"
            (source / "allure-results" / name).write_text('{"evidence":true}')
            result["attachments"].append({"name": f"Evidence {index}", "source": name, "type": "application/json"})
        result_path.write_text(json.dumps(result))
        archive = self.root / "large.zip"
        descriptor = package_bundle(source, metadata, archive)
        self.assertEqual(descriptor["sizeBytes"], archive.stat().st_size)
        extracted = self.root / "large-extracted"
        unpack(archive, extracted)
        actual = validate_bundle(extracted)
        self.assertGreater(len(actual["files"]), 10_000)
        self.assertEqual(len(actual["files"]), 10_008)
        self.assertEqual(len(read_json(next((extracted / "allure-results").glob("*-result.json")))["attachments"]), 10_002)
        (extracted / "allure-results/evidence-10000-attachment.json").write_text('{"tampered":true}')
        with self.assertRaisesRegex(ValueError, "checksum"):
            validate_bundle(extracted)

    def test_schema_accepts_its_bounded_file_limit_and_rejects_the_next_entry(self):
        metadata = fixture(self.root / "limit-source")
        metadata["files"] = {f"allure-results/{index}.json": {"sha256": "a" * 64, "sizeBytes": 1}
                             for index in range(MAX_BUNDLE_FILES)}
        self.assertEqual(MAX_BUNDLE_FILES, 50_000)
        validate_schema(metadata, "bundle")
        metadata["files"]["one-too-many.json"] = {"sha256": "b" * 64, "sizeBytes": 1}
        with self.assertRaises(ValidationError):
            validate_schema(metadata, "bundle")

    def test_extraction_counts_the_manifest_and_rejects_over_limit_before_writing(self):
        self.assertEqual(MAX_ARCHIVE, 100 * 1024 * 1024)
        self.assertEqual(MAX_UNPACKED, 500 * 1024 * 1024)
        accepted = MagicMock()
        accepted.__enter__.return_value.infolist.return_value = [zipfile.ZipInfo("bundle.json")] + [
            zipfile.ZipInfo(f"allure-results/{index}.json") for index in range(MAX_BUNDLE_FILES)]
        with patch("livedocs.zipfile.ZipFile", return_value=accepted):
            unpack("boundary.zip", self.root / "accepted-boundary")
        accepted.__enter__.return_value.extractall.assert_called_once_with(self.root / "accepted-boundary")
        entry = MagicMock(file_size=0)
        archive = MagicMock()
        archive.__enter__.return_value.infolist.return_value = [entry] * (MAX_BUNDLE_FILES + 2)
        destination = self.root / "over-limit"
        with patch("livedocs.zipfile.ZipFile", return_value=archive):
            with self.assertRaisesRegex(ValueError, "extraction limits"):
                unpack("not-opened.zip", destination)
        archive.__enter__.return_value.extractall.assert_not_called()
        self.assertFalse(destination.exists())

    def test_signed_and_untrusted_archive_urls_are_rejected(self):
        for url in ["https://example.com/report.zip", "https://account.blob.core.windows.net/reports/a.zip?sig=secret",
                    "http://account.blob.core.windows.net/reports/a.zip", "https://user:secret@account.blob.core.windows.net/a.zip"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                archive_url(url)

    def test_failed_assembly_does_not_publish_partial_snapshot(self):
        output = self.root / "new-site"
        with patch("livedocs.subprocess.check_output", return_value="3.0.0"):
            with self.assertRaisesRegex(ValueError, "Expected Allure"):
                assemble(self.manifests, self.cache, output)
        self.assertFalse(output.exists())

    def test_existing_snapshot_cannot_be_overwritten(self):
        output = self.root / "existing"
        output.mkdir()
        (output / "sentinel").write_text("last good snapshot")
        with self.assertRaisesRegex(ValueError, "already exists"):
            assemble(self.manifests, self.cache, output)
        self.assertEqual((output / "sentinel").read_text(), "last good snapshot")

    def test_empty_portal_has_version_navigation_without_fabricated_reports(self):
        self.rewrite({"schemaVersion": 1, "latestVersion": "v1", "versions": [
            {"version": "v1", "state": "development", "projects": []}]})
        output = self.root / "empty"
        assemble(self.manifests, self.cache, output, allure="missing-allure")
        self.assertIn("No service reports", (output / "livedoc/v1/index.html").read_text())
        self.assertFalse((output / "livedoc/v1/products").exists())
        self.assertTrue((output / "livedoc/catalog.json").is_file())


if __name__ == "__main__":
    unittest.main()

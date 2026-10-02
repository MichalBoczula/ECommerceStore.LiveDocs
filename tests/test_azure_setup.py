import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from azure_config import configuration, archive_references
from bundle_fixtures import create
from livedocs import read_json


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


selector = load("selector", "select-build-input.py")
aca = load("check_aca", "check-aca.py")
renderer = load("render_aca", "render-aca.py")
ENVIRONMENT = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-dev/providers/Microsoft.App/managedEnvironments/cae-ecommerce-dev"
IMAGE = "mb0101/ecommerce-store-livedocs@sha256:" + "a" * 64
VALUES = {
    "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
    "AZURE_TENANT_ID": "22222222-2222-2222-2222-222222222222",
    "AZURE_SUBSCRIPTION_ID": "33333333-3333-3333-3333-333333333333",
    "AZURE_ARCHIVE_STORAGE_ACCOUNT": "testarchive", "AZURE_ARCHIVE_CONTAINER": "livedocs",
    "AZURE_RESOURCE_GROUP": "rg-ecommerce-dev", "AZURE_CONTAINER_APPS_ENVIRONMENT": "cae-ecommerce-dev",
    "AZURE_CONTAINER_APP_NAME": "ca-ecommerce-livedocs-dev", "AZURE_APP_DEPLOYMENT_READY": "true",
}


def host():
    app = renderer.render(IMAGE, ENVIRONMENT, "northeurope", "ld-fixture")
    app["tags"] = {"managedBy": "Terraform", "component": "LiveDocs"}
    app["properties"]["configuration"]["ingress"]["fqdn"] = "fixture.azurecontainerapps.io"
    return app


class AzureSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_fresh_and_invalid_settings_fail_before_login(self):
        with self.assertRaisesRegex(ValueError, "AZURE_CLIENT_ID"):
            configuration("archive", {})
        with self.assertRaisesRegex(ValueError, "UUID"):
            configuration("archive", dict(VALUES, AZURE_CLIENT_ID="object-name"))
        with self.assertRaisesRegex(ValueError, "Provision"):
            configuration("deploy", dict(VALUES, AZURE_APP_DEPLOYMENT_READY="false"))

    def test_private_archive_is_bound_to_account_project_commit_and_digest(self):
        manifests, _ = create(self.root / "fixture")
        portal = read_json(manifests / "portal.json")
        for version in portal["versions"]:
            for reference in version["projects"]:
                reference["artifact"]["url"] = f"https://testarchive.blob.core.windows.net/livedocs/reports/{reference['project']}/{reference['commitSha']}/{reference['artifact']['sha256']}.zip"
        archive_references(portal, configuration("archive", VALUES))
        for bad in ["another.blob.core.windows.net", "/different/", "/users/", "/" + "f" * 40 + "/"]:
            changed = copy.deepcopy(portal)
            url = changed["versions"][0]["projects"][0]["artifact"]["url"]
            if bad.endswith(".net"):
                url = url.replace("testarchive.blob.core.windows.net", bad)
            elif bad == "/different/":
                url = url.replace("/livedocs/", bad)
            elif bad == "/users/":
                url = url.replace("/products/", bad)
            else:
                url = url.replace("/" + "a" * 40 + "/", bad)
            changed["versions"][0]["projects"][0]["artifact"]["url"] = url
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "boundary"):
                archive_references(changed, VALUES)

    def test_private_production_inputs_require_trusted_main(self):
        manifests, _ = create(self.root / "fixture")
        for event, ref in [("pull_request", "refs/pull/3/merge"), ("workflow_dispatch", "refs/heads/feature"), ("push", "refs/heads/feature")]:
            inputs = selector.select(manifests, event, ref, self.root / (event + "-fixtures"))
            self.assertEqual(inputs["archive_auth"], "false")
            self.assertNotEqual(Path(inputs["manifest_directory"]), manifests)
        inputs = selector.select(manifests, "push", "refs/heads/main")
        self.assertEqual(inputs["archive_auth"], "true")
        self.assertEqual(Path(inputs["manifest_directory"]), manifests)

    def test_authenticated_download_verifies_bytes_before_promoting_cache(self):
        manifests, source_cache = create(self.root / "fixture")
        portal = read_json(manifests / "portal.json")
        for version in portal["versions"]:
            for reference in version["projects"]:
                reference["artifact"]["url"] = f"https://testarchive.blob.core.windows.net/livedocs/reports/{reference['project']}/{reference['commitSha']}/{reference['artifact']['sha256']}.zip"
        (manifests / "portal.json").write_text(json.dumps(portal))
        binary = self.root / "bin"
        binary.mkdir()
        fake = binary / "az"
        fake.write_text(f'''#!{sys.executable}
import os,pathlib,shutil,sys
args=sys.argv[1:]
assert args[:3]==['storage','blob','download'] and args[args.index('--auth-mode')+1]=='login'
target=pathlib.Path(args[args.index('--file')+1])
name=args[args.index('--name')+1].split('/')[-1]
if os.environ.get('TEST_CORRUPT')=='true': target.write_bytes(b'changed archive')
else: shutil.copyfile(pathlib.Path(os.environ['TEST_CACHE'])/name,target)
''')
        fake.chmod(0o755)
        environment = dict(os.environ, **VALUES, TEST_CACHE=str(source_cache), PATH=str(binary) + os.pathsep + os.environ["PATH"])
        for corrupt in [False, True]:
            destination = self.root / ("corrupt-cache" if corrupt else "verified-cache")
            environment["TEST_CORRUPT"] = str(corrupt).lower()
            result = subprocess.run([sys.executable, "scripts/fetch-archives.py", "--azure-auth", "--manifests", str(manifests), "--cache", str(destination)], cwd=ROOT, env=environment, text=True, capture_output=True)
            if corrupt:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("checksum", result.stderr)
                self.assertEqual(list(destination.glob("*.zip")), [])
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(list(destination.glob("*.zip"))), 3)

    def test_empty_production_portal_needs_no_azure_authentication(self):
        inputs = selector.select(ROOT / "manifests", "pull_request", "refs/pull/3/merge")
        self.assertEqual(inputs["archive_auth"], "false")
        self.assertEqual(Path(inputs["manifest_directory"]), ROOT / "manifests")

    def test_host_drift_and_wrong_environment_are_rejected(self):
        self.assertEqual(aca.check(host(), ENVIRONMENT, IMAGE), "fixture.azurecontainerapps.io")
        for kind in ["environment", "ownership", "https", "probe", "scale", "image"]:
            app = host()
            if kind == "environment": app["properties"]["environmentId"] = ENVIRONMENT + "different"
            elif kind == "ownership": app["tags"] = {}
            elif kind == "https": app["properties"]["configuration"]["ingress"]["allowInsecure"] = True
            elif kind == "probe": app["properties"]["template"]["containers"][0]["probes"].pop()
            elif kind == "scale": app["properties"]["template"]["scale"]["minReplicas"] = 1
            else: app["properties"]["template"]["containers"][0]["image"] = "other:latest"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                aca.check(app, ENVIRONMENT, IMAGE)

    def test_delivery_changes_only_image_and_revision(self):
        self.bin = self.root / "bin"
        self.bin.mkdir()
        app = self.root / "app.json"
        app.write_text(json.dumps(host()))
        fake_az = self.bin / "az"
        fake_az.write_text(f'''#!{sys.executable}
import json,os,pathlib,sys
args=sys.argv[1:]
root=pathlib.Path(os.environ['TEST_ROOT'])
with (root/'calls.jsonl').open('a') as log: log.write(json.dumps(args)+'\\n')
if args[:3]==['containerapp','env','show']: print(json.dumps({{'id':{ENVIRONMENT!r},'location':'northeurope'}}))
elif args[:2]==['containerapp','show']:
 if os.environ.get('TEST_MISSING_APP')=='true': sys.exit(3)
 value=json.loads((root/'app.json').read_text())
 if (root/'updated').exists(): value['properties']['template']['containers'][0]['image']={IMAGE!r}
 print(json.dumps(value))
elif args[:2]==['containerapp','update']: (root/'updated').touch()
else: sys.exit('Unexpected Azure mutation or query')
''')
        fake_az.chmod(0o755)
        wrapper = self.bin / "python3"
        wrapper.write_text(f'''#!{sys.executable}
import os,sys
if len(sys.argv)>1 and sys.argv[1]=='scripts/smoke.py':
 assert '--expected-sha' in sys.argv and 'b'*40 in sys.argv
 print('Stubbed public smoke; actual HTTP covered by Docker CI')
else: os.execv({sys.executable!r},[{sys.executable!r}]+sys.argv[1:])
''')
        wrapper.chmod(0o755)
        environment = dict(os.environ, **VALUES, TEST_ROOT=str(self.root), PATH=str(self.bin) + os.pathsep + os.environ["PATH"])
        result = subprocess.run(["bash", "scripts/deploy-azure.sh", IMAGE, "b" * 40], cwd=ROOT, env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(row) for row in (self.root / "calls.jsonl").read_text().splitlines()]
        updates = [args for args in calls if args[:2] == ["containerapp", "update"]]
        self.assertEqual(len(updates), 1)
        self.assertIn("--image", updates[0])
        self.assertIn("--revision-suffix", updates[0])
        self.assertNotIn("--yaml", updates[0])
        (self.root / "calls.jsonl").unlink()
        environment["TEST_MISSING_APP"] = "true"
        result = subprocess.run(["bash", "scripts/deploy-azure.sh", IMAGE, "b" * 40], cwd=ROOT, env=environment, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        calls = [json.loads(row) for row in (self.root / "calls.jsonl").read_text().splitlines()]
        self.assertFalse(any(args[:2] == ["containerapp", "create"] or args[:2] == ["containerapp", "update"] for args in calls))


if __name__ == "__main__": unittest.main()

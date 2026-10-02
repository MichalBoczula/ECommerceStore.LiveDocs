#!/usr/bin/env python3
"""Prefetch private archives using Azure CLI identity; never put SAS tokens in Git."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
import urllib.parse
from livedocs import materialize, validate_manifests
from azure_config import configuration, archive_references

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manifests", type=Path, default=Path("manifests"))
parser.add_argument("--cache", type=Path, default=Path("build-input/cache"))
parser.add_argument("--azure-auth", action="store_true")
args = parser.parse_args()
portal, _ = validate_manifests(args.manifests)
if args.azure_auth:
    archive_references(portal, configuration("archive"))
args.cache.mkdir(parents=True, exist_ok=True)
for version in portal["versions"]:
    for reference in version["projects"]:
        artifact = reference["artifact"]
        destination = args.cache / f"{artifact['sha256']}.zip"
        if args.azure_auth and not destination.exists():
            url = urllib.parse.urlsplit(artifact["url"])
            container, name = urllib.parse.unquote(url.path.lstrip("/")).split("/", 1)
            with tempfile.TemporaryDirectory(dir=args.cache) as temporary:
                download = Path(temporary) / "bundle.zip"
                subprocess.run(["az", "storage", "blob", "download", "--auth-mode", "login",
                                "--account-name", url.hostname.split(".")[0], "--container-name", container,
                                "--name", name, "--file", str(download), "--output", "none"], check=True)
                if download.stat().st_size != artifact["sizeBytes"] or hashlib.sha256(download.read_bytes()).hexdigest() != artifact["sha256"]:
                    raise ValueError("Downloaded archive size/checksum mismatch")
                download.replace(destination)
        materialize(reference, args.cache)
print("Artifact cache validated")

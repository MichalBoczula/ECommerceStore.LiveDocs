#!/usr/bin/env python3
"""Prefetch and validate archives outside Docker using a bounded Azure identity."""
import argparse
from pathlib import Path
from delivery import prefetch, storage
from livedocs import materialize, validate_manifests

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manifests", type=Path, default=Path("manifests"))
parser.add_argument("--cache", type=Path, default=Path("build-input/cache"))
parser.add_argument("--azure-auth", action="store_true")
parser.add_argument("--account")
parser.add_argument("--container", default="livedocs")
args = parser.parse_args()
portal, _ = validate_manifests(args.manifests)
references = [item for version in portal["versions"] for item in version["projects"]]
if args.azure_auth:
    storage(args.account or "", args.container)
for reference in references:
    if args.azure_auth:
        prefetch(reference, args.cache, args.account, args.container)
    else:
        materialize(reference, args.cache)
print(f"Artifact cache validated: {len(references)} references")

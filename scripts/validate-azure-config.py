#!/usr/bin/env python3
import argparse
from azure_config import configuration, archive_references
from livedocs import validate_manifests

parser = argparse.ArgumentParser(description="Validate Azure configuration before login")
parser.add_argument("mode", choices=["archive", "deploy"])
args = parser.parse_args()
values = configuration(args.mode)
if args.mode == "archive":
    portal, _ = validate_manifests("manifests")
    archive_references(portal, values)
print(f"Azure {args.mode} configuration validated")

#!/usr/bin/env python3
import argparse
from pathlib import Path
from livedocs import assemble, validate_manifests

parser = argparse.ArgumentParser(description="Validate manifests and assemble a complete documentation snapshot")
parser.add_argument("--manifests", type=Path, default=Path("manifests"))
parser.add_argument("--cache", type=Path, default=Path("build-input/cache"))
parser.add_argument("--output", type=Path)
parser.add_argument("--allure", default="allure")
parser.add_argument("--previous", type=Path)
args = parser.parse_args()
if args.output:
    assemble(args.manifests, args.cache, args.output, args.allure, args.previous)
else:
    validate_manifests(args.manifests, args.previous)
print("Documentation manifests validated" if not args.output else f"Documentation assembled at {args.output}")

#!/usr/bin/env python3
"""Package staged BDD/Allure/source exports with a complete integrity inventory."""
import argparse
import json
from pathlib import Path
from livedocs import package_bundle, read_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--metadata", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
print(json.dumps(package_bundle(args.source, read_json(args.metadata), args.output), indent=2))

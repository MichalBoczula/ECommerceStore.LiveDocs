#!/usr/bin/env python3
"""Archive a verified producer bundle and publish its discovery receipt."""
import argparse
from pathlib import Path
from delivery import archive_bundle

parser = argparse.ArgumentParser(description=__doc__)
for name in ["file", "output"]:
    parser.add_argument("--" + name, type=Path, required=True)
for name in ["account", "version"]:
    parser.add_argument("--" + name, required=True)
parser.add_argument("--container", default="livedocs")
parser.add_argument("--repository")
parser.add_argument("--commit")
parser.add_argument("--run-id", type=int)
args = parser.parse_args()
archive_bundle(args.file, args.account, args.container, args.version, args.output,
               args.repository, args.commit, args.run_id)
print(f"Archived documentation; discovery receipt: {args.output}")

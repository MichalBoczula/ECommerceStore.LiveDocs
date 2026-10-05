#!/usr/bin/env python3
"""Adapt verified producer exports and Reqnroll output to the LiveDocs contract."""
import argparse
from pathlib import Path
from delivery import package_producer

parser = argparse.ArgumentParser(description=__doc__)
for name in ["source", "exports", "results", "output"]:
    parser.add_argument("--" + name, type=Path, required=True)
for name in ["features", "project", "repository", "commit"]:
    parser.add_argument("--" + name, required=True)
parser.add_argument("--run-id", type=int, required=True)
args = parser.parse_args()
print(package_producer(args.source, args.exports, args.results, args.features, args.project,
                       args.repository, args.commit, args.run_id, args.output))

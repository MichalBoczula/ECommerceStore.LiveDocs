#!/usr/bin/env python3
"""Discover successful Products runs, verify their bytes and prepare a manifest PR."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from delivery import (az, check_candidate, download, prefetch, storage,
                      update_manifest, verified_run)
from livedocs import read_json, unpack, validate_bundle, validate_manifests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--container", default="livedocs")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--project", default="products", choices=["products"])
    parser.add_argument("--manifests", type=Path, default=Path("manifests"))
    parser.add_argument("--cache", type=Path, default=Path("build-input/cache"))
    args = parser.parse_args()
    if not re.fullmatch(r"v[1-9][0-9]*", args.version):
        parser.error("Invalid documentation version")
    portal, projects = validate_manifests(args.manifests)
    selected = next((item for item in portal["versions"] if item["version"] == args.version), None)
    if selected is None or selected["state"] != "development":
        raise ValueError("Select an existing development version before importing")
    registration = projects[args.project]
    prefix = f"candidates/{args.version}/{args.project}/"
    objects = json.loads(az("list", *storage(args.account, args.container), "--prefix", prefix,
                            "--num-results", "*", "--query", "[].name", "--output", "json"))
    candidates = []
    for name in objects:
        match = re.fullmatch(re.escape(prefix) + r"([1-9][0-9]*)-([0-9a-f]{64})\.json", name)
        if not match:
            raise ValueError("Unexpected candidate path")
        candidates.append((int(match[1]), match[2], name))
    identities = {}
    for run_id, digest, _ in candidates:
        if run_id in identities and identities[run_id] != digest:
            raise ValueError("Ambiguous bundles for one producer workflow run; resolve before import")
        identities[run_id] = digest
    old = next((item for item in selected["projects"] if item["project"] == args.project), None)
    for run_id, digest, name in sorted(candidates, reverse=True):
        if old and run_id <= old["workflowRunId"]:
            continue
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            download(args.account, args.container, name, receipt_path)
            if receipt_path.stat().st_size > 65536:
                raise ValueError("Discovery receipt is too large")
            receipt = read_json(receipt_path)
            reference = check_candidate(receipt, args.version, args.project, args.account, args.container)
            if reference["workflowRunId"] != run_id or reference["artifact"]["sha256"] != digest:
                raise ValueError("Discovery receipt filename/identity mismatch")
            run = json.loads(subprocess.run(["gh", "api", f"repos/{registration['repository']}/actions/runs/{run_id}"],
                             check=True, capture_output=True, text=True).stdout)
            if not verified_run(reference, registration["repository"], run):
                continue  # Upload occurs before its owning workflow completes; try again next time.
            bundle = prefetch(reference, args.cache, args.account, args.container)
            extracted = Path(directory) / "bundle"
            unpack(bundle, extracted)
            validate_bundle(extracted, reference, registration)
            update_manifest(args.manifests, args.version, reference)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                    output.write(f"changed=true\nrun_id={run_id}\ncommit={reference['commitSha']}\n")
            print(f"Selected verified {args.project} run {run_id} for {args.version}")
            return
    print("No newer successful documentation bundle")


if __name__ == "__main__":
    main()

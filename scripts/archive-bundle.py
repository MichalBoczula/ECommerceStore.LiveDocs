#!/usr/bin/env python3
"""Upload a validated bundle to a durable, content-addressed Azure Blob path."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from livedocs import MAX_ARCHIVE, unpack, validate_bundle

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--file", type=Path, required=True)
parser.add_argument("--account", required=True)
parser.add_argument("--container", required=True)
parser.add_argument("--output", type=Path, required=True, help="Project reference to add to the version manifest")
args = parser.parse_args()
if not re.fullmatch(r"[a-z0-9]{3,24}", args.account) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])", args.container) or "--" in args.container:
    parser.error("Invalid Azure storage account or container name")
if args.file.stat().st_size > MAX_ARCHIVE:
    parser.error("Bundle exceeds archive size limit")
with tempfile.TemporaryDirectory() as temporary:
    unpack(args.file, temporary)
    metadata = validate_bundle(temporary)
digest = hashlib.sha256(args.file.read_bytes()).hexdigest()
name = f"reports/{metadata['project']}/{metadata['commitSha']}/{digest}.zip"
# Upload conflicts fail: an existing object is never overwritten or silently trusted.
subprocess.run(["az", "storage", "blob", "upload", "--auth-mode", "login", "--account-name", args.account,
                "--container-name", args.container, "--name", name, "--file", str(args.file),
                "--overwrite", "false", "--content-type", "application/zip", "--output", "none"], check=True)
reference = {key: metadata[key] for key in ["project", "commitSha", "generatedAt", "workflowRunId"]}
reference["artifact"] = {"url": f"https://{args.account}.blob.core.windows.net/{args.container}/{name}",
                         "sha256": digest, "sizeBytes": args.file.stat().st_size}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(reference, indent=2), encoding="utf-8")
print(f"Archived {metadata['project']} at commit {metadata['commitSha']}; reference: {args.output}")

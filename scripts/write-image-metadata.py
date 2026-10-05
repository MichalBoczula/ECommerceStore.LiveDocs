#!/usr/bin/env python3
"""Record the immutable published image consumed by application Infrastructure."""
import json
import os
from pathlib import Path
import re
import sys

image = os.environ["PUBLISHED_IMAGE"]
commit = os.environ["GITHUB_SHA"]
if not re.fullmatch(r"mb0101/ecommerce-store-livedocs@sha256:[0-9a-f]{64}", image):
    raise ValueError("Expected an immutable LiveDocs image digest")
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise ValueError("Expected a full LiveDocs source commit")
output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({"schemaVersion": 1, "image": image, "commitSha": commit,
                              "builtAt": os.environ["BUILD_DATE"]}, indent=2) + "\n")

#!/usr/bin/env python3
"""Declare whether the selected production manifest needs private build inputs."""
import os
from livedocs import validate_manifests

portal, _ = validate_manifests("manifests")
count = sum(len(version["projects"]) for version in portal["versions"])
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(f"required={'true' if count else 'false'}\n")
print(f"Selected archive references: {count}")

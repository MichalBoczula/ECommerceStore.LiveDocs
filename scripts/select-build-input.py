#!/usr/bin/env python3
"""Choose production inputs on trusted main runs; private archives never enter PR jobs."""
import argparse
import os
from pathlib import Path
from livedocs import validate_manifests


def select(manifests, event, ref, fixture_directory=Path("build-input/pr-fixtures")):
    portal, _ = validate_manifests(manifests)
    has_archives = any(version["projects"] for version in portal["versions"])
    trusted = event in {"push", "workflow_dispatch"} and ref == "refs/heads/main"
    directory, cache = Path(manifests), Path("build-input/cache")
    if has_archives and not trusted:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
        from bundle_fixtures import create
        directory, cache = create(fixture_directory)
        print("Untrusted/PR build uses isolated fixtures; production references are schema-checked only")
    return {"manifest_directory": str(directory), "artifact_directory": str(cache),
            "archive_auth": str(has_archives and trusted).lower()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests", type=Path, default=Path("manifests"))
    args = parser.parse_args()
    result = select(args.manifests, os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"])
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for name, value in result.items():
            output.write(f"{name}={value}\n")

#!/usr/bin/env python3
"""Reject unsuccessful or missing mandatory Actions jobs."""
import json
import os

REQUIRED = {"build", "archive-inputs", "assembly-tests", "hosting-tests", "documentation-tests",
            "dependency-audit", "secret-scan"}


def require_jobs(results, event):
    if event not in {"push", "pull_request", "workflow_dispatch"}:
        raise ValueError(f"Unsupported workflow event: {event}")
    for name in REQUIRED:
        actual = results.get(name, {}).get("result")
        if actual != "success":
            raise ValueError(f"{name} must succeed; actual result: {actual}")
    expected = "success" if event == "pull_request" else "skipped"
    actual = results.get("dependency-review", {}).get("result")
    if actual != expected:
        raise ValueError(f"Dependency Review must be {expected}; actual result: {actual}")


if __name__ == "__main__":
    require_jobs(json.loads(os.environ["NEEDS_JSON"]), os.environ["EVENT_NAME"])
    print("Every required job passed")

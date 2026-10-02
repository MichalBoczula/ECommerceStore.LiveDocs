#!/usr/bin/env python3
"""Check real generated Allure fixtures without treating them as production reports."""
import json
from pathlib import Path
import sys

site = Path(sys.argv[1]) / "livedoc"
expected = {"v1/products": ("a", "passed"), "v1/users": ("b", "passed"), "v2/products": ("c", "failed")}
catalog = json.loads((site / "catalog.json").read_text())
assert catalog["latestVersion"] == "v2"
assert '../v2/' in (site / "latest/index.html").read_text()
for route, (commit, status) in expected.items():
    project = site / route
    metadata = json.loads((project / "bundle.json").read_text())
    assert metadata["commitSha"] == commit * 40, route
    summary = json.loads((project / "allure/widgets/summary.json").read_text())
    assert summary["statistic"]["total"] == 1 and summary["statistic"][status] == 1, route
    assert (commit * 40) in (project / "index.html").read_text(), route
    assert json.loads((project / "flows.json").read_text())[0]["actionName"].endswith(commit), route
    assert list((project / "allure/data/attachments").glob("*.json")), route
assert not (site / "v2/users").exists(), "Unpublished project must not be invented"
print("Real Allure checks passed: v1 Products + Users, v2 Products, failed status, isolated source commits and attachments")

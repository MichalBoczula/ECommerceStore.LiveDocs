#!/usr/bin/env python3
"""Run a required suite with JUnit evidence, summaries and assembly coverage."""
import argparse
from pathlib import Path
import shutil
import sys
import unittest

import coverage
import xmlrunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("suite", choices=["assembly", "hosting"])
parser.add_argument("--results", type=Path, default=ROOT / "artifacts/verification")
parser.add_argument("--summary", type=Path, required=True)
args = parser.parse_args()
output = args.results / args.suite
if output.exists():
    shutil.rmtree(output)
output.mkdir(parents=True)
measurement = None
if args.suite == "assembly":
    measurement = coverage.Coverage(source=["livedocs"], data_file=str(output / ".coverage"))
    measurement.start()
module = "test_assembly.py" if args.suite == "assembly" else "test_delivery.py"
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=module)
with (output / "results.xml").open("wb") as report:
    result = xmlrunner.XMLTestRunner(output=report, verbosity=2).run(suite)
if measurement:
    measurement.stop()
    measurement.save()
    measurement.xml_report(outfile=str(output / "coverage.cobertura.xml"))
    measurement.html_report(directory=str(output / "coverage"))
    percent = measurement.report()

args.summary.parent.mkdir(parents=True, exist_ok=True)
with args.summary.open("a") as summary:
    summary.write(f"### {args.suite}\n\nTests: {result.testsRun}; failures: {len(result.failures)}; "
                  f"errors: {len(result.errors)}; skipped: {len(result.skipped)}.\n\n")
    if measurement:
        summary.write(f"Generator line coverage: {percent:.2f}% (minimum 70%).\n\n")

# Empty, skipped or unexpectedly successful suites must not produce a green gate.
passed = (result.testsRun > 0 and result.wasSuccessful() and not result.skipped
          and not result.unexpectedSuccesses and not result.expectedFailures)
if measurement and percent < 70:
    passed = False
raise SystemExit(0 if passed else 1)

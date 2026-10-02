#!/usr/bin/env python3
"""Install the exact Allure 2 distribution from the checked-in version/checksum."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request


def install(destination, archive=None):
    config = json.loads((Path(__file__).resolve().parents[1] / "tools/allure.json").read_text())
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        source = Path(archive) if archive else temporary / "allure.tgz"
        if not archive:
            with urllib.request.urlopen(config["url"], timeout=60) as response, source.open("wb") as output:
                shutil.copyfileobj(response, output)
        if hashlib.sha256(source.read_bytes()).hexdigest() != config["sha256"]:
            raise ValueError("Allure distribution checksum mismatch")
        with tarfile.open(source) as distribution:
            # The verified official distribution is trusted; reject links/path escapes anyway.
            for entry in distribution.getmembers():
                path = Path(entry.name)
                if path.is_absolute() or ".." in path.parts or entry.issym() or entry.islnk():
                    raise ValueError("Unsafe Allure archive entry")
            distribution.extractall(temporary / "unpacked", filter="data")
        shutil.copytree(temporary / "unpacked" / f"allure-{config['version']}", destination)
    print(f"Installed Allure {config['version']} at {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--archive", type=Path, help="Optional previously downloaded distribution; checksum still required")
    args = parser.parse_args()
    install(args.destination, args.archive)

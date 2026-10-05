#!/usr/bin/env python3
"""Write the exact review text without interpolating event data as shell code."""
import os
from pathlib import Path
import sys

version, run, commit = (os.environ[key] for key in ["DOC_VERSION", "SOURCE_RUN", "SOURCE_COMMIT"])
Path(sys.argv[1]).write_text(
    f"Update Products documentation for {version} from source commit `{commit}`.\n\n"
    f"The import verified the bundle inventory, identity, checksum and successful "
    f"[producer CI run](https://github.com/MichalBoczula/ProductsCatalog/actions/runs/{run}). "
    "LiveDocs CI must fetch the private inputs, generate Allure, smoke-test and scan "
    "the image before merge. Released versions remain unchanged.\n\n"
    "Merging publishes a new documentation image; application Terraform owns deployment.\n",
    encoding="utf-8")

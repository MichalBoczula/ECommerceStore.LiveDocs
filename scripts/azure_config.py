"""Validate explicit Azure identity and private archive boundaries before authentication."""
import os
import re
from urllib.parse import urlsplit, unquote

GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def configuration(mode, environment=None):
    environment = os.environ if environment is None else environment
    required = ["AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"]
    required += (["AZURE_ARCHIVE_STORAGE_ACCOUNT", "AZURE_ARCHIVE_CONTAINER"] if mode == "archive"
                 else ["AZURE_RESOURCE_GROUP", "AZURE_CONTAINER_APPS_ENVIRONMENT", "AZURE_CONTAINER_APP_NAME"])
    values = {}
    for name in required:
        value = environment.get(name, "")
        if not value:
            raise ValueError(f"Configure repository variable {name}")
        if any(char in value for char in "\r\n\t"):
            raise ValueError(f"Invalid configuration: {name}")
        values[name] = value
    for name in required[:3]:
        if not re.fullmatch(GUID, values[name]):
            raise ValueError(f"Expected a UUID for {name}")
    if mode == "archive":
        if not re.fullmatch(r"[a-z0-9]{3,24}", values["AZURE_ARCHIVE_STORAGE_ACCOUNT"]):
            raise ValueError("Invalid archive account")
        if values["AZURE_ARCHIVE_CONTAINER"] != "livedocs":
            raise ValueError("Use the dedicated livedocs archive container")
    else:
        if environment.get("AZURE_APP_DEPLOYMENT_READY") != "true":
            raise ValueError("Provision the Terraform-managed environment/app, then enable app-scoped delivery in the LiveDocs foundation first")
        for name in ["AZURE_CONTAINER_APPS_ENVIRONMENT", "AZURE_CONTAINER_APP_NAME"]:
            value = values[name]
            if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}[a-z0-9]", value) or "--" in value:
                raise ValueError(f"Invalid resource name: {name}")
    return values


def archive_references(portal, values):
    host = values["AZURE_ARCHIVE_STORAGE_ACCOUNT"] + ".blob.core.windows.net"
    container = values["AZURE_ARCHIVE_CONTAINER"]
    for version in portal["versions"]:
        for reference in version["projects"]:
            artifact = reference["artifact"]
            url = urlsplit(artifact["url"])
            expected = f"/{container}/reports/{reference['project']}/{reference['commitSha']}/{artifact['sha256']}.zip"
            if url.hostname != host or unquote(url.path) != expected:
                raise ValueError("Archive reference is outside the configured content-addressed project/commit boundary")

#!/usr/bin/env python3
"""Render the dedicated ACA app specification as JSON (also valid YAML)."""
import argparse
import json
import re


def render(image, environment_id, location, revision):
    if not re.fullmatch(r"(?:docker\.io/)?mb0101/ecommerce-store-livedocs@sha256:[0-9a-f]{64}", image):
        raise ValueError("Deploy an immutable digest from mb0101/ecommerce-store-livedocs")
    if not re.fullmatch(r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.App/managedEnvironments/[^/]+", environment_id, re.IGNORECASE):
        raise ValueError("An existing Container Apps environment resource ID is required")
    if not location or not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", revision) or "--" in revision or revision.endswith("-"):
        raise ValueError("Location and a valid unique revision suffix are required")
    probes = []
    for kind, path, delay, period, failures in [
        ("Startup", "/health/ready", 1, 2, 30),
        ("Readiness", "/health/ready", 3, 5, 3),
        ("Liveness", "/health/live", 10, 10, 3),
    ]:
        probes.append({"type": kind, "httpGet": {"path": path, "port": 8080},
                       "initialDelaySeconds": delay, "periodSeconds": period,
                       "timeoutSeconds": 2, "failureThreshold": failures})
    return {
        "location": location,
        "properties": {
            "environmentId": environment_id,
            "configuration": {
                "activeRevisionsMode": "Single",
                "maxInactiveRevisions": 5,
                "ingress": {"external": True, "targetPort": 8080, "transport": "http",
                            "allowInsecure": False, "traffic": [{"latestRevision": True, "weight": 100}]},
            },
            "template": {
                "revisionSuffix": revision,
                "containers": [{"name": "livedocs", "image": image,
                                "resources": {"cpu": 0.25, "memory": "0.5Gi"}, "probes": probes}],
                "scale": {"minReplicas": 0, "maxReplicas": 1,
                          "rules": [{"name": "http", "http": {"metadata": {"concurrentRequests": "10"}}}]},
            },
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["image", "environment-id", "location", "revision"]:
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.image, args.environment_id, args.location, args.revision), indent=2))
    except ValueError as error:
        parser.error(str(error))

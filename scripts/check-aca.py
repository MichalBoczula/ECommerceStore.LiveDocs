#!/usr/bin/env python3
"""Refuse deployment when Terraform host configuration or ownership has drifted."""
import argparse
import json


def check(app, environment_id, expected_image=None):
    properties = app["properties"]
    actual = properties.get("environmentId") or properties.get("managedEnvironmentId")
    if not actual or actual.lower() != environment_id.lower():
        raise ValueError("Existing app belongs to a different ACA environment")
    tags = app.get("tags", {})
    if tags.get("managedBy") != "Terraform" or tags.get("component") != "LiveDocs":
        raise ValueError("Create the app through the LiveDocs Terraform module in Infrastructure state first")
    config = properties["configuration"]
    ingress = config["ingress"]
    if (config["activeRevisionsMode"] != "Single" or not ingress.get("external")
            or ingress.get("allowInsecure") is not False or ingress["targetPort"] != 8080
            or ingress.get("transport") != "http" or config.get("maxInactiveRevisions") != 5):
        raise ValueError("Restore the Terraform-managed HTTPS ingress and revision configuration")
    template = properties["template"]
    containers = template["containers"]
    if len(containers) != 1 or containers[0]["name"] != "livedocs":
        raise ValueError("Expected one livedocs container")
    container = containers[0]
    if container["resources"] != {"cpu": 0.25, "memory": "0.5Gi"}:
        # Azure may add computed resource fields; compare only the owned allocation.
        if container["resources"].get("cpu") != 0.25 or container["resources"].get("memory") != "0.5Gi":
            raise ValueError("Restore the Terraform-managed CPU/memory allocation")
    probes = {probe["type"]: probe.get("httpGet", {}) for probe in container.get("probes", [])}
    expected = {"Startup": "/health/ready", "Readiness": "/health/ready", "Liveness": "/health/live"}
    if set(probes) != set(expected) or any(probes[k].get("port") != 8080 or probes[k].get("path") != v for k, v in expected.items()):
        raise ValueError("Restore the Terraform-managed HTTP probes")
    scale = template["scale"]
    rules = scale.get("rules", [])
    if scale.get("minReplicas", 0) != 0 or scale.get("maxReplicas") != 1 or len(rules) != 1 or str(rules[0].get("http", {}).get("metadata", {}).get("concurrentRequests")) != "10":
        raise ValueError("Restore Terraform-managed HTTP scale-to-zero configuration")
    if expected_image and container["image"] != expected_image:
        raise ValueError("Azure app does not reference the requested immutable image")
    return ingress["fqdn"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app")
    parser.add_argument("environment_id")
    parser.add_argument("--expected-image")
    args = parser.parse_args()
    with open(args.app, encoding="utf-8") as source:
        print(check(json.load(source), args.environment_id, args.expected_image))

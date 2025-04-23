#!/usr/bin/env python3

"""
cloud_deploy.py

Unified deployment script for all Cloud Run services in the hygiene prediction pipeline.

Key features:
1. Tags and pushes Docker images to Artifact Registry for all services.
2. Deploys `trigger` with a generated SERVICE_CONFIG_B64 (URLs of all services).
3. Deploys all other microservices with appropriate environment variables, including TRIGGER_URL.
4. Works for individual services via --only or full pipeline if no --only is provided.
5. Supports --dry-run mode to preview all actions.

Usage:
    python3 cloud_deploy.py                      # Full deployment
    python3 cloud_deploy.py --only extractor     # Deploy single service
    python3 cloud_deploy.py --dry-run            # Preview only
"""

import subprocess
import json
import base64
import argparse

ALL_SERVICES = [
    "extractor",
    "cleaner",
    "loader-json",
    "loader-parquet",
    "trigger",
    "eda-dashboard"
]

REGISTRY = "us-central1-docker.pkg.dev/hygiene-prediction/containers"

def run(cmd, desc, dry_run=False):
    print(f"\n🔧 {desc}...")
    print(f"🔍 Command: {cmd}")
    if dry_run:
        print("💡 Dry-run mode: not executing.")
        return
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed: {desc}")
        exit(result.returncode)

def get_service_url(name):
    cmd = [
        "gcloud", "run", "services", "describe", name,
        "--platform=managed", "--region=us-central1",
        "--format=value(status.url)"
    ]
    return subprocess.check_output(cmd).decode().strip()

def deploy_service(service, env_vars, dry_run=False):
    remote_tag = f"{REGISTRY}/{service}"
    run(
        f"gcloud run deploy {service} "
        f"--image={remote_tag} "
        f"--platform=managed "
        f"--region=us-central1 "
        f"--allow-unauthenticated "
        f"--memory=1Gi "
        f"--timeout=600 "
        f"--set-env-vars={env_vars}",
        f"Deploying {service} to Cloud Run",
        dry_run
    )

def build_env(service, trigger_url):
    env_vars = f"HTTP_MODE=true"

    if service != "trigger":
        env_vars += f",TRIGGER_URL={trigger_url}/clean"

    if service == "extractor":
        env_vars += ",BUCKET_NAME=raw-inspection-data"

    elif service == "cleaner":
        env_vars += (
            ",BUCKET_NAME=raw-inspection-data"
            ",RAW_PREFIX=raw-data"
            ",CLEAN_PREFIX=clean-data"
            ",CLEAN_ROW_BUCKET_NAME=cleaned-inspection-data-row"
            ",CLEAN_COL_BUCKET_NAME=cleaned-inspection-data-column"
        )

    elif service == "loader-json":
        env_vars += (
            ",BUCKET_NAME=cleaned-inspection-data-row"
            ",BQ_DATASET=HygienePredictionRow"
            ",BQ_TABLE=CleanedInspectionRow"
        )

    elif service == "loader-parquet":
        env_vars += (
            ",BUCKET_NAME=cleaned-inspection-data-column"
            ",BQ_DATASET=HygienePredictionColumn"
            ",BQ_TABLE=CleanedInspectionColumn"
        )

    return env_vars

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview all commands without executing")
    parser.add_argument("--only", help="Deploy only a specific service (e.g., 'cleaner')")
    args = parser.parse_args()

    dry_run = args.dry_run
    only_service = args.only

    print("🚀 Starting cloud_deploy.py")

    # === Handle --only mode ===
    if only_service:
        local_tag = f"hygiene_prediction-{only_service}"
        remote_tag = f"{REGISTRY}/{only_service}"

        run(f"docker tag {local_tag} {remote_tag}", f"Tagging {only_service}", dry_run)
        run(f"gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://{REGISTRY.split('/')[0]}", "Authenticating Docker", dry_run)
        run(f"docker push {remote_tag}", f"Pushing {only_service}", dry_run)

        if only_service == "trigger":
            urls = {
                "extractor": get_service_url("extractor") + "/extract",
                "cleaner": get_service_url("cleaner") + "/clean",
                "loader": get_service_url("loader-json") + "/load",
                "loader_parquet": get_service_url("loader-parquet") + "/load",
                "trigger": get_service_url("trigger") + "/clean"
            }
            config_b64 = base64.b64encode(json.dumps({k: {"url": v} for k, v in urls.items()}).encode()).decode()
            env_vars = f"SERVICE_CONFIG_B64={config_b64},HTTP_MODE=true"
        else:
            trigger_url = get_service_url("trigger")
            env_vars = build_env(only_service, trigger_url)

        deploy_service(only_service, env_vars, dry_run)
        return

    # === Phase 1: Tag + push all services ===
    for service in ALL_SERVICES:
        local_tag = f"hygiene_prediction-{service}"
        remote_tag = f"{REGISTRY}/{service}"

        run(f"docker tag {local_tag} {remote_tag}", f"Tagging {service}", dry_run)
        run(f"gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://{REGISTRY.split('/')[0]}", "Authenticating Docker", dry_run)
        run(f"docker push {remote_tag}", f"Pushing {service}", dry_run)

    # === Phase 2: Deploy non-trigger services with proper env vars ===
    trigger_url = get_service_url("trigger")
    for service in ALL_SERVICES:
        if service in ["trigger", "eda-dashboard"]:
            continue
        env_vars = build_env(service, trigger_url)
        deploy_service(service, env_vars, dry_run)

    # === Phase 3: Deploy trigger with SERVICE_CONFIG_B64 ===
    print("\n📡 Building SERVICE_CONFIG_B64 for trigger...")
    urls = {
        "extractor": get_service_url("extractor") + "/extract",
        "cleaner": get_service_url("cleaner") + "/clean",
        "loader": get_service_url("loader-json") + "/load",
        "loader_parquet": get_service_url("loader-parquet") + "/load",
        "trigger": get_service_url("trigger") + "/clean"
    }
    config_json = json.dumps({k: {"url": v} for k, v in urls.items()})
    config_b64 = base64.b64encode(config_json.encode()).decode()
    env_vars = f"SERVICE_CONFIG_B64={config_b64},HTTP_MODE=true"
    deploy_service("trigger", env_vars, dry_run)

    print("\n✅ All services deployed with full routing configuration.")

if __name__ == "__main__":
    main()

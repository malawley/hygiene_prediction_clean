#!/usr/bin/env python3

"""
cloud_deploy.py

Unified deployment script for all Cloud Run services in the hygiene prediction pipeline.
This script ensures correct deployment order, pushes service images, injects inter-service configuration, 
and optionally provisions infrastructure (GCS, BigQuery, Artifact Registry, APIs).

Key features:
1. Tags and pushes Docker images to Artifact Registry for all services.
2. Optionally provisions infrastructure (buckets, datasets, APIs) with --check-infra.
3. Deploys `trigger` first with placeholder config to enable early availability.
4. Deploys all other services (`extractor`, `cleaner`, `loader-json`, `loader-parquet`) 
   with the real `TRIGGER_URL` from the running trigger service.
5. Rebuilds and redeploys `trigger` with full SERVICE_CONFIG_B64 after collecting all service URLs.

After successful execution:
- `trigger` holds a complete routing map (`SERVICE_CONFIG_B64`) of all other services.
- All other services receive the real `TRIGGER_URL` for sending events.
- The pipeline is fully connected and ready to execute via an HTTP `/run` call.

Usage examples:
    # Full deploy (fast, no infra checks)
    $ python3 cloud_deploy.py

    # Full deploy with infrastructure provisioning
    $ python3 cloud_deploy.py --check-infra

    # Dry run preview
    $ python3 cloud_deploy.py --dry-run

    # Deploy only the cleaner
    $ python3 cloud_deploy.py --only cleaner

Options:
    --only          Deploy only a single service (e.g., "cleaner")
    --dry-run       Print all deployment commands without executing them
    --check-infra   Verify and create infrastructure (GCS, BigQuery, APIs) before deploy
"""



import os
import json
import base64
import argparse
import subprocess  # ✅ Only once (you had it twice)

# 🔧 Load services.json for global deployment config
with open("src/configure/services.json", "r") as f:
    services_config = json.load(f)

PROJECT = services_config["project"]
REGION = services_config["region"]
ALL_SERVICES = services_config["all_services"]
REGISTRY = f"{REGION}-docker.pkg.dev/{PROJECT}/containers"

# 🔐 Auto-encode services.json as base64 for Cloud Run if not already set
if "SERVICE_CONFIG_B64" not in os.environ:
    with open("src/configure/services.json", "rb") as f_raw:
        encoded = base64.b64encode(f_raw.read()).decode("utf-8")
        os.environ["SERVICE_CONFIG_B64"] = encoded
        print("🔐 Loaded SERVICE_CONFIG_B64 from src/configure/services.json")


def ensure_required_apis(project_id):
    ...

    required_apis = [
        "run.googleapis.com",
        "storage.googleapis.com",
        "bigquery.googleapis.com",
        "artifactregistry.googleapis.com",
        "iam.googleapis.com",
        "cloudbuild.googleapis.com",
        "logging.googleapis.com"
    ]
    for api in required_apis:
        print(f"🔎 Ensuring API enabled: {api}")
        subprocess.run([
            "gcloud", "services", "enable", api,
            "--project", project_id
        ], check=False)


def ensure_gcs_buckets(project_id):
    required_buckets = [
        "raw-inspection-data-434",
        "cleaned-inspection-data-row-434",
        "cleaned-inspection-data-column-434"
    ]
    for bucket in required_buckets:
        full_uri = f"gs://{bucket}"
        print(f"🔎 Checking GCS bucket: {full_uri}")
        result = subprocess.run(
            ["gsutil", "ls", "-p", project_id, full_uri],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if result.returncode != 0:
            print(f"🪣 Creating GCS bucket: {full_uri}")
            subprocess.run([
                "gsutil", "mb", "-p", project_id, "-l", "us-central1", full_uri
            ], check=True)

def ensure_bq_datasets(project_id):
    required_datasets = ["HygienePredictionRow", "HygienePredictionColumn"]
    for dataset in required_datasets:
        print(f"🔎 Checking BigQuery dataset: {dataset}")
        result = subprocess.run(
            ["bq", "ls", "--project_id", project_id],
            capture_output=True,
            text=True
        )
        if dataset not in result.stdout:
            print(f"📊 Creating BigQuery dataset: {dataset}")
            subprocess.run([
                "bq", "mk", "--location=US", "--project_id", project_id, dataset
            ], check=True)

def ensure_artifact_repo(project_id, region, repo_name="containers"):
    print(f"🔎 Checking if Artifact Registry repo '{repo_name}' exists in {region}...")

    result = subprocess.run([
        "gcloud", "artifacts", "repositories", "describe", repo_name,
        "--location", region,
        "--project", project_id
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"📦 Artifact Registry repo not found. Creating '{repo_name}'...")
        create_cmd = [
            "gcloud", "artifacts", "repositories", "create", repo_name,
            "--repository-format=docker",
            "--location", region,
            "--project", project_id
        ]
        subprocess.run(create_cmd, check=True)
        print(f"✅ Repository '{repo_name}' created.")
    else:
        print(f"✅ Artifact Registry repo '{repo_name}' already exists.")


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
        dry_run=dry_run
    )
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview all commands without executing")
    parser.add_argument("--only", help="Deploy only a specific service (e.g., 'cleaner')")
    parser.add_argument("--check-infra", action="store_true", help="Ensure required infrastructure (APIs, buckets, datasets)")
    args = parser.parse_args()

    dry_run = args.dry_run
    only_service = args.only
    check_infra = args.check_infra

    print("🚀 Starting cloud_deploy.py")

    if only_service:
        if check_infra and not dry_run:
            ensure_required_apis(PROJECT)
            ensure_artifact_repo(PROJECT, REGION)
            ensure_gcs_buckets(PROJECT)
            ensure_bq_datasets(PROJECT)

        local_tag = f"hygiene_prediction-{only_service}"
        remote_tag = f"{REGISTRY}/{only_service}"

        run(f"docker tag {local_tag} {remote_tag}", f"Tagging {only_service}", dry_run)
        run(f"gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://{REGISTRY.split('/')[0]}", "Authenticating Docker", dry_run)
        run(f"docker push {remote_tag}", f"Pushing {only_service}", dry_run)

        if only_service == "trigger":
            env_vars = ""
        else:
            trigger_url = get_service_url("trigger") + "/clean"
            env_vars = f"TRIGGER_URL={trigger_url}"

        deploy_service(only_service, env_vars, dry_run)
        return

    if check_infra and not dry_run:
        ensure_required_apis(PROJECT)
        ensure_artifact_repo(PROJECT, REGION)
        ensure_gcs_buckets(PROJECT)
        ensure_bq_datasets(PROJECT)

    # === Phase 1: Build and push all images
    for service in ALL_SERVICES:
        local_tag = f"hygiene_prediction-{service}"
        remote_tag = f"{REGISTRY}/{service}"

        run(f"docker tag {local_tag} {remote_tag}", f"Tagging {service}", dry_run)
        run(f"gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://{REGISTRY.split('/')[0]}", "Authenticating Docker", dry_run)
        run(f"docker push {remote_tag}", f"Pushing {service}", dry_run)

    # === Phase 2: Deploy trigger first
    print("\n🚀 Deploying trigger with minimal config...")
    deploy_service("trigger", "SERVICE_CONFIG_B64=eyJ0cmlnZ2VyIjp7InVybCI6Imh0dHA6Ly9wbGFjZWhvbGRlciJ9fQ==", dry_run)


    # === Phase 3: Deploy other services with real TRIGGER_URL
    print("\n🔗 Deploying services with real TRIGGER_URL...")
    trigger_url = get_service_url("trigger") + "/clean"
    for service in ALL_SERVICES:
        if service in ["trigger", "eda-dashboard"]:
            continue
        env_vars_dict = services_config.get(service, {}).copy()
        env_vars_dict["TRIGGER_URL"] = trigger_url
        env_vars = ",".join(f"{k}={v}" for k, v in env_vars_dict.items())
        deploy_service(service, env_vars, dry_run)

    # === Phase 4: Redeploy trigger with SERVICE_CONFIG_B64
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
    env_vars = f"SERVICE_CONFIG_B64={config_b64}"
    deploy_service("trigger", env_vars, dry_run)

    print("\n✅ All services deployed with full routing configuration.")

if __name__ == "__main__":
    main()

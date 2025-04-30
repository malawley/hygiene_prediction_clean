#!/usr/bin/env python3

import subprocess
import json
import base64

def get_service_url(name):
    cmd = [
        "gcloud", "run", "services", "describe", name,
        "--platform=managed", "--region=us-central1",
        "--format=value(status.url)"
    ]
    return subprocess.check_output(cmd).decode().strip()

def main():
    print("🔍 Fetching Cloud Run service URLs...")
    urls = {
        "extractor": get_service_url("extractor") + "/extract",
        "cleaner": get_service_url("cleaner") + "/clean",
        "loader": get_service_url("loader-json") + "/load",
        "loader_parquet": get_service_url("loader-parquet") + "/load",
        "trigger": get_service_url("trigger") + "/clean"
    }

    service_config = {key: {"url": value} for key, value in urls.items()}
    config_json = json.dumps(service_config)
    config_b64 = base64.b64encode(config_json.encode()).decode()

    def deploy(service_name, image_tag, extra_env=""):
        env_vars = f"SERVICE_CONFIG_B64={config_b64}"
        if extra_env:
            env_vars += f",{extra_env}"

        print(f"🚀 Redeploying {service_name}...")
        subprocess.run([
            "gcloud", "run", "deploy", service_name,
            "--image", f"us-central1-docker.pkg.dev/hygiene-prediction-434/containers/{image_tag}",
            "--platform=managed",
            "--region=us-central1",
            "--allow-unauthenticated",
            "--memory=1Gi",
            "--timeout=300",
            "--set-env-vars", env_vars
        ], check=True)
        print(f"✅ {service_name} successfully redeployed.")

    deploy("trigger", "trigger", "HTTP_MODE=true")

    deploy("extractor", "extractor",
        "BUCKET_NAME=raw-inspection-data,"
        "HTTP_MODE=true")

    deploy("cleaner", "cleaner",
        "BUCKET_NAME=raw-inspection-data,"
        "RAW_PREFIX=raw-data,CLEAN_PREFIX=clean-data,"
        "CLEAN_ROW_BUCKET_NAME=cleaned-inspection-data-row,"
        "CLEAN_COL_BUCKET_NAME=cleaned-inspection-data-column,"
        "HTTP_MODE=true")

    deploy("loader-json", "loader-json",
        "BUCKET_NAME=cleaned-inspection-data-row,"
        "BQ_DATASET=HygienePredictionRow,BQ_TABLE=CleanedInspectionRow,"
        "HTTP_MODE=true")

    deploy("loader-parquet", "loader-parquet",
        "BUCKET_NAME=cleaned-inspection-data-column,"
        "BQ_DATASET=HygienePredictionColumn,BQ_TABLE=CleanedInspectionColumn,"
        "HTTP_MODE=true")


if __name__ == "__main__":
    main()

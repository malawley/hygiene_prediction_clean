#!/usr/bin/env python3

import subprocess

SERVICES = [
    "extractor",
    "cleaner",
    "loader-json",
    "loader-parquet",
    "trigger",
    "eda-dashboard"
]

REGISTRY = "us-central1-docker.pkg.dev/hygiene-prediction/containers"
TRIGGER_URL = "https://trigger-wrja4w3inq-uc.a.run.app/clean"
               
def run(cmd, desc):
    print(f"\n🔧 {desc}...")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed: {desc}")
        exit(result.returncode)

def main():
    print("🚀 Starting deploy_images.py...")

    for service in SERVICES:
        local_tag = f"hygiene_prediction-{service}"
        remote_tag = f"{REGISTRY}/{service}"

        # Tag
        run(f"docker tag {local_tag} {remote_tag}", f"Tagging {service}")

        # Push
        run(f"gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://{REGISTRY.split('/')[0]}", "Authenticating Docker")
        run(f"docker push {remote_tag}", f"Pushing {service}")

        # Set env vars
        env_vars = "HTTP_MODE=true"
        if service not in ["trigger", "eda-dashboard"]:
            env_vars += f",TRIGGER_URL={TRIGGER_URL}"

        # Deploy
        run(
            f"gcloud run deploy {service} "
            f"--image={remote_tag} "
            f"--platform=managed "
            f"--region=us-central1 "
            f"--allow-unauthenticated "
            f"--memory=1Gi "
            f"--timeout=600 "
            f"--set-env-vars={env_vars}",
            f"Deploying {service} to Cloud Run"
        )

    print("\n✅ All services pushed and deployed to Cloud Run.")

if __name__ == "__main__":
    main()

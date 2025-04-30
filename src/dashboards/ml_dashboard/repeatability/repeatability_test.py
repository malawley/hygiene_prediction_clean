import requests
import time
import json
from pathlib import Path

# === CONFIGURATION ===
FASTAPI_URL = "http://localhost:8090/generate_report"
CONFIG_DIR = Path("repeatability/configure_test_files")
REPORT_DIR = Path("repeatability/reports")

# === SETUP ===
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# === RUN TESTS FOR EACH CONFIG ===
for config_file in sorted(CONFIG_DIR.glob("*.json")):
    with open(config_file) as f:
        config = json.load(f)

    config_name = config["name"]
    print(f"\n🔁 Sending: {config_name}")

    # Step 1: Send POST request to FastAPI
    response = requests.post(FASTAPI_URL, json=config)
    if response.status_code != 200:
        print(f"❌ Request failed for {config_name}: {response.status_code}")
        print(response.text)
        continue

    # Step 2: Get download URL
    response_json = response.json()
    download_url = response_json.get("download_url")
    if not download_url:
        print(f"❌ No download_url in response for {config_name}")
        continue

    print(f"⬇️  Downloading report for {config_name} from: {download_url}")

    # Step 3: Download the report
    csv_response = requests.get(download_url)
    if csv_response.status_code != 200:
        print(f"❌ Failed to download report for {config_name}: {csv_response.status_code}")
        continue

    # Step 4: Save to reports directory
    output_file = REPORT_DIR / f"{config_name}.csv"
    with open(output_file, "wb") as f:
        f.write(csv_response.content)

    print(f"✅ Report saved: {output_file}")
    time.sleep(1)

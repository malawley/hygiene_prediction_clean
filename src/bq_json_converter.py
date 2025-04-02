import json
import io
import logging
from google.cloud import storage
from google.auth import default
from google.cloud.exceptions import NotFound
import argparse
from datetime import datetime

# === Logging Setup ===
logger = logging.getLogger("bq_json_converter")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")

file_handler = logging.FileHandler("logs/bq_json_converter.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-row"
NDJSON_PREFIX = "clean-data-ndjson"
INPUT_PREFIX = "clean-data"

def log_active_credentials():
    credentials, project = default()
    logger.info(f"Using ADC credentials for project: {project}")
    logger.info(f"Credentials type: {type(credentials)}")
    if hasattr(credentials, 'quota_project_id'):
        logger.info(f"Quota project ID: {credentials.quota_project_id}")
    if hasattr(credentials, 'service_account_email'):
        logger.info(f"Service Account: {credentials.service_account_email}")
    print(f"🔐 Using credentials for project: {project}")

def load_manifest(client, date: str):
    manifest_blob_path = f"{INPUT_PREFIX}/{date}/_manifest.json"
    bucket = client.bucket(BUCKET_NAME)
    manifest_blob = bucket.blob(manifest_blob_path)

    if not manifest_blob.exists():
        logger.warning(f"No manifest found at {manifest_blob_path}")
        print(f"⚠️ No manifest found for {date}")
        return []

    manifest_content = json.loads(manifest_blob.download_as_text())
    if not manifest_content.get("upload_complete", False):
        logger.info(f"Manifest found, but not marked complete.")
        print(f"⚠️ Manifest for {date} not marked complete.")
        return []

    return manifest_content["files"]

def convert_and_save_ndjson(blob_name: str, date: str):
    logger.info(f"Starting NDJSON conversion for: {blob_name}")
    print(f"🔄 Converting: {blob_name}")
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        blob = bucket.blob(f"{INPUT_PREFIX}/{date}/{blob_name}")
        content = blob.download_as_text()
        data = json.loads(content)

        # Convert to NDJSON in memory
        ndjson_buffer = io.StringIO()
        for row in data:
            ndjson_buffer.write(json.dumps(row) + "\n")

        new_blob_name = f"{NDJSON_PREFIX}/{date}/{blob_name.replace('.json', '.ndjson')}"
        new_blob = bucket.blob(new_blob_name)
        new_blob.upload_from_string(ndjson_buffer.getvalue(), content_type="application/json")

        logger.info(f"Uploaded NDJSON: {new_blob_name}")
        print(f"✅ Uploaded: {new_blob_name}")

    except Exception as e:
        logger.exception(f"Failed to process {blob_name}: {e}")
        print(f"❌ Error: {blob_name} (see log for details)")

def main(date: str):
    logger.info(f"=== Starting JSON to NDJSON conversion for {date} ===")
    print(f"🚀 Starting NDJSON conversion for {date}...")

    try:
        client = storage.Client()
        files = load_manifest(client, date)
        if not files:
            logger.info("No files listed for conversion.")
            return

        ndjson_files = []
        for filename in files:
            json_filename = filename.replace(".ndjson", ".json")
            convert_and_save_ndjson(json_filename, date)
            ndjson_filename = filename  # filenames from cleaner already have .ndjson
            ndjson_files.append(ndjson_filename)

        # ✨ Write _manifest.json for NDJSON output
        manifest_data = {
            "upload_complete": True,
            "files": ndjson_files
        }
        manifest_blob_path = f"{NDJSON_PREFIX}/{date}/_manifest.json"
        bucket = client.bucket(BUCKET_NAME)
        manifest_blob = bucket.blob(manifest_blob_path)
        manifest_blob.upload_from_string(json.dumps(manifest_data), content_type="application/json")
        logger.info(f"Wrote NDJSON manifest to gs://{BUCKET_NAME}/{manifest_blob_path}")
        print(f"📝 Wrote NDJSON manifest to gs://{BUCKET_NAME}/{manifest_blob_path}")

        logger.info(f"=== Finished NDJSON conversion for {date} ===")
        print(f"🎉 Export complete: {len(ndjson_files)} file(s) converted and uploaded.")

    except Exception as e:
        logger.exception(f"Fatal error during JSON to NDJSON conversion: {e}")
        print("❌ Fatal error — see log for details.")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert cleaned JSON to NDJSON")
    parser.add_argument("--date", type=str, default=None, help="Date to convert in YYYY-MM-DD format")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    log_active_credentials()
    main(date_str)

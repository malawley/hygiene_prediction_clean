import json
import io
import logging
from google.cloud import storage

# === Logging Setup ===
logger = logging.getLogger("bq_loader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")

# Write to: logs/bq_loader_run.log
file_handler = logging.FileHandler("logs/bq_loader_run.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-row-434"
NDJSON_PREFIX = "clean-data-ndjson"
INPUT_PREFIX = "clean-data"

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
    logger.info(f"=== Starting BigQuery NDJSON export for {date} ===")
    print(f"🚀 Starting NDJSON export for {date}...")
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        blobs = bucket.list_blobs(prefix=f"{INPUT_PREFIX}/{date}/")
        count = 0
        for blob in blobs:
            if blob.name.endswith(".json"):
                filename = blob.name.split("/")[-1]
                convert_and_save_ndjson(filename, date)
                count += 1

        logger.info(f"=== Finished NDJSON export for {date} ===")
        print(f"🎉 Export complete: {count} file(s) converted and uploaded.")

    except Exception as e:
        logger.exception(f"Error during BigQuery NDJSON export: {e}")
        print("❌ Fatal error — see log for details.")

if __name__ == "__main__":
    main("2025-03-30")

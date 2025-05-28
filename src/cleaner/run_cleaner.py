import os
import base64
import sys
import time
import json
import logging
import requests
import io
from io import BytesIO
from datetime import datetime
from google.cloud import storage
import polars as pl
from werkzeug.wrappers import Request, Response

# === Logging Setup ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s'
)
logger = logging.getLogger(__name__)

# === Cleaner Imports ===
from app.cleaner import (
    cleaner_1_drop,
    cleaner_2_inspection_id,
    cleaner_3_text_normalization,
    cleaner_4_values_consolidation,
    cleaner_5_facility_type,
    cleaner_6_inspection_type,
    cleaner_7_results,
    cleaner_8_geolocation,
    cleaner_9_tokenize_violations,
)

# === Load TRIGGER_URL from env or SERVICE_CONFIG_B64 ===
TRIGGER_URL = os.environ.get("TRIGGER_URL")

if not TRIGGER_URL:
    config_b64 = os.environ.get("SERVICE_CONFIG_B64")
    if config_b64:
        try:
            decoded = base64.b64decode(config_b64).decode()
            service_config = json.loads(decoded)
            TRIGGER_URL = service_config.get("trigger", {}).get("url")
        except Exception as e:
            logger.error(f"❌ Failed to parse SERVICE_CONFIG_B64: {e}")

if not TRIGGER_URL:
    raise ValueError("❌ TRIGGER_URL is not set in env or SERVICE_CONFIG_B64")

# === Notify Trigger ===
def post_back_to_trigger(payload, trigger_url):
    if not trigger_url:
        logger.warning("⚠️ Trigger URL not set — skipping POST back")
        return
    try:
        logger.info(f"📤 Sending payload to trigger: {json.dumps(payload)}")
        response = requests.post(trigger_url, json=payload)
        logger.info(f"📤 POST to trigger returned: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"❌ Failed to POST back to trigger: {e}")


# === Config (Cloud Native) ===
BUCKET_NAME = os.environ["RAW_BUCKET"]
RAW_PREFIX = os.environ.get("RAW_PREFIX", "raw-data")
CLEAN_PREFIX = os.environ.get("CLEAN_PREFIX", "clean-data")
CLEAN_ROW_BUCKET_NAME = os.environ.get("CLEAN_ROW_BUCKET_NAME", "cleaned-inspection-data-row-434")
CLEAN_COL_BUCKET_NAME = os.environ.get("CLEAN_COL_BUCKET_NAME", "cleaned-inspection-data-column-434")

# === GCS Clients ===
storage_client = storage.Client()
raw_bucket = storage_client.bucket(BUCKET_NAME)
clean_row_bucket = storage_client.bucket(CLEAN_ROW_BUCKET_NAME)
clean_col_bucket = storage_client.bucket(CLEAN_COL_BUCKET_NAME)

# === Helper: Load Manifest ===
def load_manifest(date: str):
    manifest_path = f"{RAW_PREFIX}/{date}/_manifest.json"
    blob = raw_bucket.blob(manifest_path)

    if not blob.exists():
        logger.warning(f"⚠️ No manifest found at {manifest_path}")
        return []

    try:
        manifest = json.loads(blob.download_as_text())
    except Exception as e:
        logger.error(f"❌ Failed to load or parse manifest: {e}")
        return []

    if not manifest.get("upload_complete"):
        logger.info(f"Manifest for {date} not marked complete. Skipping.")
        return []

    logger.info(f"📦 Loaded manifest with {len(manifest['files'])} files for {date}")
    return manifest["files"]


# === Helper: Download Raw File ===
def download_json_as_polars_blob(path: str):
    blob = raw_bucket.blob(path)

    if not blob.exists():
        logger.error(f"❌ GCS blob not found: {path}")
        return None

    try:
        raw_bytes = blob.download_as_bytes()
        df = pl.read_ndjson(BytesIO(raw_bytes))
    except Exception as e:
        logger.error(f"❌ Failed to download or parse NDJSON from {path}: {e}")
        return None

    if df.is_empty():
        logger.warning(f"⚠️ Parsed empty DataFrame from {path}")
        return None

    return df


# === Helper: Upload Cleaned File ===# === Helper: Upload Cleaned File ===
# === Helper: Upload Cleaned File ===
def upload_polars_to_gcs(df: pl.DataFrame, base_path: str):
    json_path = f"{CLEAN_PREFIX}/{base_path}.json"
    json_blob = clean_row_bucket.blob(json_path)
    
    parquet_path = f"{CLEAN_PREFIX}/{base_path}.parquet"
    parquet_blob = clean_col_bucket.blob(parquet_path)

    # Upload NDJSON
    try:
        ndjson_data = df.write_ndjson()
        json_blob.upload_from_string(ndjson_data, content_type="application/x-ndjson")
        logger.info(f"✅ Uploaded NDJSON to: {json_path}")
    except Exception as e:
        logger.error(f"❌ Failed to upload NDJSON to {json_path}: {e}")

    # Upload Parquet
    try:
        parquet_buffer = BytesIO()
        df.write_parquet(parquet_buffer)
        parquet_buffer.seek(0)
        parquet_blob.upload_from_file(parquet_buffer, content_type="application/octet-stream")
        logger.info(f"✅ Uploaded Parquet to: {parquet_path}")
    except Exception as e:
        logger.error(f"❌ Failed to upload Parquet to {parquet_path}: {e}")

    # Return file names (not full GCS paths)
    base_filename = base_path.split("/")[-1]
    return f"{base_filename}.json", f"{base_filename}.parquet"



# === Cleaning Pipeline ===
# === Cleaning Pipeline ===
def run_cleaning_pipeline(df: pl.DataFrame) -> pl.DataFrame:
    steps = [
        cleaner_1_drop,
        cleaner_2_inspection_id,
        cleaner_3_text_normalization,
        cleaner_4_values_consolidation,
        cleaner_5_facility_type,
        cleaner_6_inspection_type,
        cleaner_7_results,
        cleaner_8_geolocation,
        cleaner_9_tokenize_violations,
    ]

    for step in steps:
        df = step(df, logger)
    return df


def notify_trigger(date: str, files_cleaned: int, total_files: int, duration: float, trigger_url: str):
    payload = {
        "event": "cleaner_completed",
        "origin": "cleaner",
        "date": date,
        "status": "completed",
        "files_cleaned": files_cleaned,
        "total_files": total_files,
        "message": f"✅ Finished cleaning for {date} | Files cleaned: {files_cleaned}/{total_files}",
        "timestamp": datetime.utcnow().isoformat(),
        "duration": str(round(duration, 3))
    }

    if not trigger_url:
        logger.error("❌ No trigger URL provided — not notifying trigger.")
        return

    try:
        logger.info(f"📤 Sending payload to trigger: {payload}")
        response = requests.post(trigger_url, json=payload, timeout=30)
        logger.info(f"📤 POST to trigger returned: {response.status_code} {response.text}")
    except requests.exceptions.Timeout:
        logger.error("❌ Trigger POST timed out.")
    except Exception as e:
        logger.exception(f"❌ Unexpected error posting to trigger: {e}")




# === Main ===
def main(date: str):
    start = time.time()
    ndjson_files = []
    parquet_files = []

    logger.info(f"=== Starting cleaning for {date} ===")
    files = load_manifest(date)
    if not files:
        logger.warning(f"No files to process for {date}")
        return

    cleaned_count = 0

    for filename in files:
        raw_path = f"{RAW_PREFIX}/{date}/{filename}"
        base_name = filename.replace(".json", "")
        try:
            logger.info(f"📄 Processing file: {filename}")
            df = download_json_as_polars_blob(raw_path)
            if df is None:
                continue

            df_clean = run_cleaning_pipeline(df)
            json_name, parquet_name = upload_polars_to_gcs(df_clean, f"{date}/{base_name}")
            ndjson_files.append(json_name)
            parquet_files.append(parquet_name)
            cleaned_count += 1
        except Exception as e:
            logger.exception(f"❌ Error processing file {filename}: {e}")

    # Write NDJSON manifest
    ndjson_manifest_path = f"{CLEAN_PREFIX}/{date}/_manifest.json"
    manifest_blob = clean_row_bucket.blob(ndjson_manifest_path)
    manifest_blob.upload_from_string(
        json.dumps({"upload_complete": True, "files": ndjson_files}),
        content_type="application/json"
    )
    logger.info(f"📝 Wrote NDJSON manifest to: {ndjson_manifest_path}")

    # Write Parquet manifest
    parquet_manifest_path = f"{CLEAN_PREFIX}/{date}/_manifest.json"
    manifest_blob_col = clean_col_bucket.blob(parquet_manifest_path)
    manifest_blob_col.upload_from_string(
        json.dumps({"upload_complete": True, "files": parquet_files}),
        content_type="application/json"
    )
    logger.info(f"📝 Wrote Parquet manifest to: {parquet_manifest_path}")

    summary_msg = f"✅ Finished cleaning for {date} | Files cleaned: {cleaned_count}/{len(files)}"
    logger.info(f"=== {summary_msg} ===")

    duration = time.time() - start

    notify_trigger(
        date=date,
        files_cleaned=cleaned_count,
        total_files=len(files),
        duration=duration,
        trigger_url=TRIGGER_URL
    )


# === HTTP Entry Point ===
def http_entry_point(request):
    """Cloud Run / HTTP function entry point."""
    if request.path == "/health":
        return ("ok", 200, {"Content-Type": "text/plain"})
    
    try:
        request_json = request.get_json()
        if not request_json:
            return ("Invalid or missing JSON body", 400, {"Content-Type": "text/plain"})

        logger.info(f"📥 Received HTTP request: {request_json}")
        date = request_json.get("date")
        if not date:
            return ("Missing 'date' in request JSON", 400, {"Content-Type": "text/plain"})

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return ("Invalid 'date' format. Use YYYY-MM-DD.", 400, {"Content-Type": "text/plain"})

        main(date)
        return (f"✅ Cleaning started for {date}", 200, {"Content-Type": "text/plain"})

    except Exception as e:
        logger.exception(f"❌ HTTP request failed: {e}")
        return (f"❌ Server error: {str(e)}", 500, {"Content-Type": "text/plain"})


def wsgi_app(environ, start_response):
    request = Request(environ)
    response_text, status, headers = http_entry_point(request)
    response = Response(response_text, status=status, headers=headers)
    return response(environ, start_response)

import os
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

# === Load Services Configuration ===
def load_services_config(path=None):
    if not path:
        path = os.getenv("SERVICE_CONFIG_PATH", "/app/services.json")
        print(f"Trying to load services config from: {path}")


    with open(path, "r") as f:
        return json.load(f)

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



# === Config ===
BUCKET_NAME = os.getenv("BUCKET_NAME", "raw-inspection-data")
RAW_PREFIX = os.getenv("RAW_PREFIX", "raw-data")
CLEAN_PREFIX = os.getenv("CLEAN_PREFIX", "clean-data")
CLEAN_ROW_BUCKET_NAME = os.getenv("CLEAN_ROW_BUCKET_NAME", "cleaned-inspection-data-row")
CLEAN_COL_BUCKET_NAME = os.getenv("CLEAN_COL_BUCKET_NAME", "cleaned-inspection-data-column")
LOG_FILE = os.getenv("LOG_FILE", "src/logs/cleaner_run.log")
MODE = os.getenv("RUN_MODE", "local")  # Options: "local", "http", "cloud"

# === Logging Setup ===
handlers = [logging.StreamHandler()]

if MODE in ("local", "http"):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    handlers.append(logging.FileHandler(LOG_FILE))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)

# === Load trigger URL from config ===
SERVICES = load_services_config()
TRIGGER_URL = SERVICES.get("trigger", {}).get("url")
logger.info(f"📡 Loaded trigger URL: {TRIGGER_URL}")

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
        logger.warning(f"No manifest found for date: {date}")
        return []
    manifest = json.loads(blob.download_as_text())
    if not manifest.get("upload_complete"):
        logger.info(f"Manifest for {date} not marked complete. Skipping.")
        return []
    logger.info(f"Loaded manifest with {len(manifest['files'])} files for {date}")
    return manifest["files"]

# === Helper: Download Raw File ===
def download_json_as_polars_blob(path: str):
    blob = raw_bucket.blob(path)
    if not blob.exists():
        logger.error(f"Missing file in GCS: {path}")
        return None
    try:
        raw_bytes = blob.download_as_bytes()
        stream = BytesIO(raw_bytes)
        df = pl.read_ndjson(stream)
        if df.is_empty():
            logger.warning(f"⚠️ Parsed empty DataFrame from {path}")
            return None
        return df
    except Exception as e:
        logger.error(f"Failed to parse JSON from {path}: {e}")
        return None


# === Helper: Upload Cleaned File ===# === Helper: Upload Cleaned File ===
def upload_polars_to_gcs(df: pl.DataFrame, base_path: str):
    json_path = f"{CLEAN_PREFIX}/{base_path}.json"
    json_blob = clean_row_bucket.blob(json_path)
    parquet_path = f"{CLEAN_PREFIX}/{base_path}.parquet"
    parquet_blob = clean_col_bucket.blob(parquet_path)

    try:
        ndjson_data = df.write_ndjson()
        json_blob.upload_from_string(ndjson_data, content_type='application/x-ndjson')
        logger.info(f"✅ Uploaded NDJSON to: {json_path}")
    except Exception as e:
        logger.error(f"❌ Upload failed (NDJSON) for {json_path}: {e}")

    try:
        parquet_buffer = BytesIO()
        df.write_parquet(parquet_buffer)
        parquet_buffer.seek(0)
        parquet_blob.upload_from_file(parquet_buffer, content_type='application/octet-stream')
        logger.info(f"✅ Uploaded Parquet to: {parquet_path}")
    except Exception as e:
        logger.error(f"❌ Upload failed (Parquet) for {parquet_path}: {e}")

    # Return only the filenames (not full paths)
    json_filename = f"{base_path.split('/')[-1]}.json"
    parquet_filename = f"{base_path.split('/')[-1]}.parquet"
    return json_filename, parquet_filename


# === Cleaning Pipeline ===
def run_cleaning_pipeline(df: pl.DataFrame) -> pl.DataFrame:
    df = cleaner_1_drop(df, logger)
    df = cleaner_2_inspection_id(df, logger)
    df = cleaner_3_text_normalization(df, logger)
    df = cleaner_4_values_consolidation(df, logger)
    df = cleaner_5_facility_type(df, logger)
    df = cleaner_6_inspection_type(df, logger)
    df = cleaner_7_results(df, logger)
    df = cleaner_8_geolocation(df, logger)
    df = cleaner_9_tokenize_violations(df, logger)
    return df


def notify_trigger(date: str, files_cleaned: int, total_files: int, duration: float, trigger_url: str):
    payload = {
        "event": "cleaner_completed",
        "origin": "cleaner",
        "date": date,
        "status": "completed",
        "files_cleaned": str(files_cleaned),
        "total_files": str(total_files),
        "message": f"✅ Finished cleaning for {date} | Files cleaned: {files_cleaned}/{total_files}",
        "timestamp": datetime.utcnow().isoformat(),
        "duration": str(round(duration, 3))
    }

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
            logger.info(f"Processing file: {filename}")
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
    manifest_ndjson = {
        "upload_complete": True,
        "files": ndjson_files
    }
    manifest_blob = clean_row_bucket.blob(f"{CLEAN_PREFIX}/{date}/_manifest.json")
    manifest_blob.upload_from_string(json.dumps(manifest_ndjson), content_type="application/json")
    logger.info(f"📝 Wrote NDJSON manifest to: {CLEAN_PREFIX}/{date}/_manifest.json")

    # Write Parquet manifest
    manifest_parquet = {
        "upload_complete": True,
        "files": parquet_files
    }
    manifest_blob_col = clean_col_bucket.blob(f"{CLEAN_PREFIX}/{date}/_manifest.json")
    manifest_blob_col.upload_from_string(json.dumps(manifest_parquet), content_type="application/json")
    logger.info(f"📝 Wrote Parquet manifest to: {CLEAN_PREFIX}/{date}/_manifest.json")

    summary_msg = f"✅ Finished cleaning for {date} | Files cleaned: {cleaned_count}/{len(files)}"
    logger.info(f"=== {summary_msg} ===")

    duration = time.time() - start

    # ✅ New helper function used here
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


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python run_cleaner.py YYYY-MM-DD")
    else:
        try:
            date = sys.argv[1]
            datetime.strptime(date, "%Y-%m-%d")
            print(f"🚀 Starting cleaner for {date}")

            start = time.time()
            main(date)
            duration = round(time.time() - start, 3)

            print("✅ Cleaning finished.")

            # Notify trigger
            payload = {
                "event": "cleaner_completed",
                "date": date,
                "origin": "cleaner",
                "duration": str(duration)
            }
            resp = requests.post("http://trigger:8080/clean", json=payload)
            print(f"📤 Notified trigger: {resp.status_code} {resp.text}")

        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")

def wsgi_app(environ, start_response):
    request = Request(environ)
    response_text, status, headers = http_entry_point(request)
    response = Response(response_text, status=status, headers=headers)
    return response(environ, start_response)

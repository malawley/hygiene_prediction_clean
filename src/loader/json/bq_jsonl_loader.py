import json
import logging
import requests
import time
import os
from google.cloud import bigquery, storage
from google.auth import default
from google.cloud.exceptions import NotFound
import argparse
from datetime import datetime
from werkzeug.wrappers import Request, Response


# === Logging Setup ===
logger = logging.getLogger("bq_ndjson_loader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")

# Log to file
file_handler = logging.FileHandler("logs/bq_ndjson_loader.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Log to terminal
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)



# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-row"
GCS_PREFIX = "clean-data"
BQ_PROJECT = "hygiene-prediction"
BQ_DATASET = "HygienePredictionRow"
BQ_TABLE = "CleanedInspectionRow"

def log_active_credentials():
    credentials, project = default()
    logger.info(f"Using ADC credentials for project: {project}")
    logger.info(f"Credentials type: {type(credentials)}")
    if hasattr(credentials, 'quota_project_id'):
        logger.info(f"Quota project ID: {credentials.quota_project_id}")
    if hasattr(credentials, 'service_account_email'):
        logger.info(f"Service Account: {credentials.service_account_email}")
    print(f"🔐 Using credentials for project: {project}")

def ensure_dataset_exists(bq_client, dataset_id: str):
    try:
        bq_client.get_dataset(dataset_id)
        logger.info(f"Dataset already exists: {dataset_id}")
        print(f"✅ Dataset found: {dataset_id}")
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        bq_client.create_dataset(dataset)
        logger.info(f"Created dataset: {dataset_id}")
        print(f"🆕 Created dataset: {dataset_id}")
    except Exception as e:
        logger.exception(f"Unexpected error checking creating dataset: {e}")
        raise

def load_manifest(storage_client, date: str):
    manifest_path = f"{GCS_PREFIX}/{date}/_manifest.json"
    bucket = storage_client.bucket(BUCKET_NAME)
    manifest_blob = bucket.blob(manifest_path)

    if not manifest_blob.exists():
        logger.warning(f"No manifest found at {manifest_path}")
        print(f"⚠️ No manifest found for {date}")
        return []

    manifest = json.loads(manifest_blob.download_as_text())
    if not manifest.get("upload_complete", False):
        logger.info(f"Manifest found but not marked complete.")
        print(f"⚠️ Manifest not marked complete for {date}")
        return []

    return manifest["files"]

def load_ndjson_to_bigquery(date: str):
    print(f"🚀 Starting BigQuery NDJSON load for {date}...")
    # ⏱️ Start timing
    start = time.time()
    storage_client = storage.Client()
    bq_client = bigquery.Client()

    dataset_id = f"{BQ_PROJECT}.{BQ_DATASET}"
    ensure_dataset_exists(bq_client, dataset_id)

    files = load_manifest(storage_client, date)
    if not files:
        logger.info("No files listed in manifest. Skipping.")
        return

    count = 0
    for filename in files:
        gcs_uri = f"gs://{BUCKET_NAME}/{GCS_PREFIX}/{date}/{filename}"
        logger.info(f"Loading file into BigQuery: {gcs_uri}")
        print(f"⏳ Loading: {filename}")

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=True,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=["ALLOW_FIELD_ADDITION"],
        )

        table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

        try:
            load_job = bq_client.load_table_from_uri(
                gcs_uri, table_id, job_config=job_config
            )
            load_job.result()
            logger.info(f"Loaded: {filename} into {table_id}")
            print(f"✅ Loaded: {filename}")
            count += 1
        except Exception as e:
            logger.exception(f"Failed to load {filename}: {e}")
            print(f"❌ ERROR loading {filename} — see log")

    print(f"🎉 BigQuery NDJSON load complete: {count} file(s) processed.")
    # Notify trigger to launch column loader
    # Compute Duration
    duration = round(time.time() - start, 3)  # ✅ Compute duration
    payload = {
        "event": "loader_json_completed",
        "origin": "json_loader",
        "date": date,
        "files_processed": str(count),
        "timestamp": datetime.utcnow().isoformat(),
        "duration": str(duration)
    }

    trigger_url = os.getenv("TRIGGER_URL", "http://trigger:8080/clean")
    try:
        logger.info(f"📤 Posting to trigger: {payload}")
        response = requests.post(trigger_url, json=payload)
        logger.info(f"📤 Trigger response: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"❌ Failed to notify trigger: {e}")

    

# === HTTP Entry Point ===
def http_entry_point(request):
    try:
        request_json = request.get_json()
        logger.info(f"📥 Received HTTP request: {request_json}")
        date = request_json.get("date")
        if not date:
            return ("Missing 'date' in request", 400, {"Content-Type": "text/plain"})

        # Start timer
        start = time.time()
        log_active_credentials()
        load_ndjson_to_bigquery(date)
        duration = round(time.time() - start, 3)

        # Respond early
        response_text = f"✅ NDJSON load complete for {date}"
        response = (response_text, 200, {"Content-Type": "text/plain"})

        # Notify trigger in background
        def notify():
            payload = {
                "event": "loader_json_completed",
                "origin": "json_loader",
                "date": date,
                "duration": str(duration),
                "timestamp": datetime.utcnow().isoformat()
            }
            try:
                logger.info(f"📤 Posting to trigger: {payload}")
                response = requests.post(os.getenv("TRIGGER_URL", "http://trigger:8080/clean"), json=payload)
                logger.info(f"📤 Trigger response: {response.status_code} {response.text}")
            except Exception as e:
                logger.error(f"❌ Failed to notify trigger: {e}")

        import threading
        threading.Thread(target=notify).start()

        return response

    except Exception as e:
        logger.exception("❌ Loader failed")
        return (f"❌ Server error: {str(e)}", 500, {"Content-Type": "text/plain"})




def wsgi_app(environ, start_response):
    request = Request(environ)
    response_text, status, headers = http_entry_point(request)
    response = Response(response_text, status=status, headers=headers)
    return response(environ, start_response)

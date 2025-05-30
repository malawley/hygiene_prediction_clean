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

# === Logging Setup (Cloud Native) ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
logger = logging.getLogger("bq_parquet_loader")

# === Config from Environment ===
BUCKET_NAME = os.environ["BUCKET_NAME"]
GCS_PREFIX = os.environ.get("GCS_PREFIX", "clean-data")
BQ_PROJECT = os.environ.get("BQ_PROJECT", "hygiene-prediction-434")
BQ_DATASET = os.environ.get("BQ_DATASET", "HygienePredictionColumn")
BQ_TABLE = os.environ.get("BQ_TABLE", "CleanedInspectionColumn")

# === Trigger URL from environment or SERVICE_CONFIG_B64 ===
trigger_url = os.environ.get("TRIGGER_URL")

if not trigger_url:
    config_b64 = os.environ.get("SERVICE_CONFIG_B64")
    if config_b64:
        try:
            decoded = base64.b64decode(config_b64).decode()
            service_config = json.loads(decoded)
            trigger_url = service_config.get("trigger", {}).get("url")
            logger.info(f"📡 Loaded trigger URL from SERVICE_CONFIG_B64: {trigger_url}")
        except Exception as e:
            logger.error(f"❌ Failed to parse SERVICE_CONFIG_B64: {e}")

if not trigger_url:
    logger.warning("⚠️ Trigger URL is not set — downstream notifications will be skipped")



def ensure_dataset_exists(bq_client, dataset_id: str):
    try:
        bq_client.get_dataset(dataset_id)
        logger.info(f"✅ Dataset exists: {dataset_id}")
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "US"
        bq_client.create_dataset(dataset)
        logger.info(f"🆕 Created dataset: {dataset_id}")
    except Exception as e:
        logger.exception(f"❌ Error checking or creating dataset: {dataset_id}")
        raise

def log_active_credentials():
    credentials, project = default()
    logger.info(f"🔐 Using ADC credentials for project: {project}")
    logger.info(f"Credentials type: {type(credentials)}")
    if hasattr(credentials, "quota_project_id"):
        logger.info(f"Quota project ID: {credentials.quota_project_id}")
    if hasattr(credentials, "service_account_email"):
        logger.info(f"Service Account: {credentials.service_account_email}")


def ensure_table_parquet(table_name: str, date: str):
    """Ensures a BigQuery table exists. Creates it using the first Parquet file if missing."""
    logger.info(f"🔍 Checking BigQuery table: {table_name}")

    client = bigquery.Client()
    storage_client = storage.Client()

    table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{table_name}"
    dataset_id = f"{BQ_PROJECT}.{BQ_DATASET}"

    ensure_dataset_exists(client, dataset_id)

    try:
        client.get_table(table_id)
        logger.info(f"✅ Table exists: {table_id}")
        return
    except NotFound:
        logger.warning(f"🆕 Table not found: {table_id}, attempting to create...")

    files = load_manifest(storage_client, date)
    if not files:
        logger.error(f"❌ No files found for {date}, cannot create table.")
        return

    source_uri = f"gs://{BUCKET_NAME}/{GCS_PREFIX}/{date}/{files[0]}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        autodetect=True
    )

    logger.info(f"📥 Creating table {table_id} from {source_uri}")
    load_job = client.load_table_from_uri(source_uri, table_id, job_config=job_config)
    load_job.result()
    logger.info(f"✅ Created table: {table_id}")



def load_manifest(storage_client, date: str):
    manifest_path = f"{GCS_PREFIX}/{date}/_manifest.json"
    bucket = storage_client.bucket(BUCKET_NAME)
    manifest_blob = bucket.blob(manifest_path)

    if not manifest_blob.exists():
        logger.warning(f"⚠️ No manifest found at: gs://{BUCKET_NAME}/{manifest_path}")
        return []

    try:
        manifest = json.loads(manifest_blob.download_as_text())
    except Exception as e:
        logger.error(f"❌ Failed to parse manifest at {manifest_path}: {e}")
        return []

    if not manifest.get("upload_complete", False):
        logger.info(f"⚠️ Manifest for {date} found but not marked complete.")
        return []

    file_count = len(manifest.get("files", []))
    logger.info(f"📦 Loaded manifest for {date} with {file_count} file(s).")

    return manifest.get("files", [])


def load_parquet_to_bigquery(date: str):
    logger.info(f"🚀 Starting BigQuery Parquet load for {date}...")
    start = time.time()

    storage_client = storage.Client()
    bq_client = bigquery.Client()

    dataset_id = f"{BQ_PROJECT}.{BQ_DATASET}"
    ensure_dataset_exists(bq_client, dataset_id)

    files = load_manifest(storage_client, date)
    if not files:
        logger.info(f"⚠️ No files listed in manifest for {date}. Skipping load.")
        return 0, 0.0

    count = 0
    for filename in files:
        gcs_uri = f"gs://{BUCKET_NAME}/{GCS_PREFIX}/{date}/{filename}"
        table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

        logger.info(f"⏳ Loading Parquet file into BigQuery: {gcs_uri}")

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=["ALLOW_FIELD_ADDITION"],
        )

        try:
            load_job = bq_client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
            load_job.result()
            logger.info(f"✅ Loaded: {filename} into {table_id}")
            count += 1
        except Exception as e:
            logger.exception(f"❌ Failed to load {filename} into BigQuery: {e}")

    duration = round(time.time() - start, 3)
    logger.info(f"🎉 BigQuery Parquet load complete: {count} file(s) processed in {duration} seconds.")

    payload = {
        "event": "loader_parquet_completed",
        "origin": "parquet_loader",
        "date": date,
        "files_processed": str(count),
        "timestamp": datetime.utcnow().isoformat(),
        "duration": str(duration),
    }

    if trigger_url:
        try:
            logger.info(f"📤 Posting to trigger: {payload}")
            response = requests.post(trigger_url, json=payload, timeout=30)
            logger.info(f"📤 Trigger response: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"❌ Failed to notify trigger: {e}")
    else:
        logger.warning("⚠️ No valid trigger URL — skipping trigger notification.")

    return count, duration

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

        # Optional: strict format check (same as cleaner)
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return ("Invalid 'date' format. Use YYYY-MM-DD.", 400, {"Content-Type": "text/plain"})

        log_active_credentials()
        ensure_table_parquet(BQ_TABLE, date)
        files_processed, duration = load_parquet_to_bigquery(date)

        return (f"✅ Parquet load complete for {date}", 200, {"Content-Type": "text/plain"})

    except Exception as e:
        logger.exception("❌ HTTP request failed")
        return (f"❌ Server error: {str(e)}", 500, {"Content-Type": "text/plain"})

def health_check(environ, start_response):
    response = Response("OK", status=200, content_type="text/plain")
    return response(environ, start_response)

# def wsgi_app(environ, start_response):
#     request = Request(environ)
#     if request.path == "/health":
#         return health_check(environ, start_response)
#     else:
#         response_text, status, headers = http_entry_point(request)
#         response = Response(response_text, status=status, headers=headers)
#         return response(environ, start_response)

def wsgi_app(environ, start_response):
    request = Request(environ)
    response_text, status, headers = http_entry_point(request)
    response = Response(response_text, status=status, headers=headers)
    return response(environ, start_response)


# def wsgi_app(environ, start_response):
#     request = Request(environ)
#     response_text, status, headers = http_entry_point(request)
#     response = Response(response_text, status=status, headers=headers)
#     return response(environ, start_response)

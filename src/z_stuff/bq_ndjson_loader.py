import json
import logging
from google.cloud import bigquery, storage
from google.auth import default
from google.cloud.exceptions import NotFound
import argparse
from datetime import datetime


# === Logging Setup ===
logger = logging.getLogger("bq_ndjson_loader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
file_handler = logging.FileHandler("logs/bq_ndjson_loader.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-row"
GCS_PREFIX = "clean-data-ndjson"
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load NDJSON files to BigQuery")
    parser.add_argument("--date", type=str, default=None, help="Date to load in YYYY-MM-DD format")
    args = parser.parse_args()

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    log_active_credentials()
    load_ndjson_to_bigquery(date_str)

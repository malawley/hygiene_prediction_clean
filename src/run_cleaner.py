import json
import logging
from datetime import datetime
from google.cloud import storage
import polars as pl
import os
import io
from io import StringIO
import json
import argparse
from google.auth import default


# === Cleaner Imports ===
from cleaner.cleaner import (
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


# === Config ===
RAW_BUCKET = "raw-inspection-data"
RAW_PREFIX = "raw-data"

ROW_BUCKET = "cleaned-inspection-data-row"
COL_BUCKET = "cleaned-inspection-data-column"
CLEAN_PREFIX = "clean-data"

LOG_FILE = "logs/cleaner_run.log"

def log_active_credentials():
    credentials, project = default()
    logger.info(f"Using ADC credentials for project: {project}")
    logger.info(f"Credentials type: {type(credentials)}")
    logger.info(f"Credentials scopes: {credentials.scopes if hasattr(credentials, 'scopes') else 'N/A'}")
    if hasattr(credentials, 'service_account_email'):
        logger.info(f"Service Account: {credentials.service_account_email}")
    if hasattr(credentials, 'quota_project_id'):
        logger.info(f"Quota project ID: {credentials.quota_project_id}")
    print(f"🔐 Using credentials for project: {project}")


# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# === Logging Setup ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === GCS Client ===
storage_client = storage.Client()
bucket = storage_client.bucket(RAW_BUCKET)

# === Helper: Load Manifest ===
def load_manifest(date: str):
    manifest_path = f"{RAW_PREFIX}/{date}/_manifest.json"
    blob = bucket.blob(manifest_path)
    if not blob.exists():
        logger.warning(f"No manifest found for date: {date}")
        return []
    manifest = json.loads(blob.download_as_text())
    if not manifest.get("upload_complete"):
        logger.info(f"Manifest for {date} not marked complete. Skipping.")
        return []
    return manifest["files"][:4]

# === Helper: Download Raw File ===
def download_json_as_polars_blob(gcs_path: str) -> pl.DataFrame:
    """
    Downloads a raw JSON file from GCS and loads it into a Polars DataFrame.
    """
    blob = bucket.blob(gcs_path)
    raw_text = blob.download_as_text()
    return pl.read_json(StringIO(raw_text))  # ✅ wrap string as file-like


# === Helper: Upload Cleaned File ===
def ensure_bucket_exists(bucket_name: str):
    client = storage.Client()
    try:
        client.get_bucket(bucket_name)
        print(f"✅ GCS bucket exists: {bucket_name}")
    except Exception as e:
        print(f"🆕 Creating GCS bucket: {bucket_name}")
        client.create_bucket(bucket_name, location="US")  # ⚠️ Adjust region if needed


def upload_polars_json_to_gcs(df: pl.DataFrame, date: str, filename: str, logger=None):
    """Upload DataFrame to GCS as row-oriented JSON."""
    bucket_name = "cleaned-inspection-data-row"
    ensure_bucket_exists(bucket_name)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"clean-data/{date}/{filename}")

    # Serialize to row-oriented JSON
    json_str = df.write_json(row_oriented=True)
    blob.upload_from_string(json_str, content_type="application/json")

    if logger:
        logger.info(f"Uploaded JSON to gs://{bucket_name}/clean-data/{date}/{filename}")
    else:
        print(f"✅ Uploaded JSON to gs://{bucket_name}/clean-data/{date}/{filename}")


def upload_polars_parquet_to_gcs(df: pl.DataFrame, date: str, filename: str, logger=None):
    """Upload DataFrame to GCS as Parquet (columnar format)."""
    bucket_name = "cleaned-inspection-data-column"
    ensure_bucket_exists(bucket_name)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(f"clean-data/{date}/{filename.replace('.json', '.parquet')}")

    # Write to in-memory buffer as Parquet
    buffer = io.BytesIO()
    df.write_parquet(buffer)
    buffer.seek(0)
    blob.upload_from_file(buffer, content_type="application/octet-stream")

    if logger:
        logger.info(f"Uploaded Parquet to gs://{bucket_name}/clean-data/{date}/{filename.replace('.json', '.parquet')}")
    else:
        print(f"✅ Uploaded Parquet to gs://{bucket_name}/clean-data/{date}/{filename.replace('.json', '.parquet')}")



# === Cleaning Pipeline ===
def run_cleaning_pipeline(df: pl.DataFrame) -> pl.DataFrame:
    def log_step(name, df):
        logger.info(f"{name}: shape = {df.shape}")
        print(f"{name}: shape = {df.shape}")
        if df.is_empty():
            logger.warning(f"{name} returned an empty DataFrame!")
            print(f"⚠️ {name} returned an empty DataFrame!")

    df = cleaner_1_drop(df, logger)
    log_step("After cleaner_1_drop", df)

    df = cleaner_2_inspection_id(df, logger)
    log_step("After cleaner_2_inspection_id", df)

    df = cleaner_3_text_normalization(df, logger)
    log_step("After cleaner_3_text_normalization", df)

    df = cleaner_4_values_consolidation(df, logger)
    log_step("After cleaner_4_values_consolidation", df)

    df = cleaner_5_facility_type(df, logger)
    log_step("After cleaner_5_facility_type", df)

    df = cleaner_6_inspection_type(df, logger)
    log_step("After cleaner_6_inspection_type", df)

    df = cleaner_7_results(df, logger)
    log_step("After cleaner_7_results", df)

    df = cleaner_8_geolocation(df, logger)
    log_step("After cleaner_8_geolocation", df)

    df = cleaner_9_tokenize_violations(df, logger)
    log_step("After cleaner_9_tokenize_violations", df)

    return df


# === Main ===
def main(date: str):
    logger.info(f"=== Starting cleaning for {date} ===")
    files = load_manifest(date)
    if not files:
        return

    cleaned_files = []

    for filename in files:
        raw_path = f"{RAW_PREFIX}/{date}/{filename}"
        try:
            logger.info(f"Processing file: {filename}")
            df = download_json_as_polars_blob(raw_path)
            if df is None:
                continue

            df_clean = run_cleaning_pipeline(df)

            # Upload row-oriented JSON for ML
            upload_polars_json_to_gcs(df_clean, date, filename, logger)

            # Upload column-oriented Parquet for dashboards
            upload_polars_parquet_to_gcs(df_clean, date, filename, logger)

            cleaned_files.append(filename.replace(".json", ".ndjson"))

        except Exception as e:
            logger.exception(f"Error processing file {filename}: {e}")

    # Write manifest to both cleaned buckets
    def write_manifest(bucket_name, extension):
        manifest_data = {
            "upload_complete": True,
            "files": [f.replace(".json", extension) for f in files]
        }
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"{CLEAN_PREFIX}/{date}/_manifest.json")
        blob.upload_from_string(json.dumps(manifest_data), content_type="application/json")
        logger.info(f"Wrote _manifest.json to gs://{bucket_name}/{CLEAN_PREFIX}/{date}/")

    write_manifest(ROW_BUCKET, ".ndjson")
    write_manifest(COL_BUCKET, ".parquet")

    logger.info(f"=== Finished cleaning for {date} ===")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run cleaning pipeline")
    parser.add_argument("--date", type=str, default=None, help="Date to clean in YYYY-MM-DD format")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = datetime.today().strftime("%Y-%m-%d")

    log_active_credentials()
    main(date_str)

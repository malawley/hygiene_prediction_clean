import json
import logging
from datetime import datetime
from google.cloud import storage
import polars as pl

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
BUCKET_NAME = "raw-inspection-data"
RAW_PREFIX = "raw-data"
CLEAN_PREFIX = "clean-data"
LOG_FILE = "cleaner_run.log"

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
bucket = storage_client.bucket(BUCKET_NAME)

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
    return manifest["files"]

# === Helper: Download Raw File ===
def download_json_as_polars_blob(path: str):
    blob = bucket.blob(path)
    if not blob.exists():
        logger.error(f"Missing file in GCS: {path}")
        return None
    raw_text = blob.download_as_text()
    return pl.read_json(raw_text)

# === Helper: Upload Cleaned File ===
def upload_polars_to_gcs(df: pl.DataFrame, path: str):
    blob = bucket.blob(path)
    blob.upload_from_string(df.write_json(row_oriented=True), content_type='application/json')
    logger.info(f"Uploaded cleaned file to: {path}")

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

# === Main ===
def main(date: str):
    logger.info(f"=== Starting cleaning for {date} ===")
    files = load_manifest(date)
    if not files:
        return

    for filename in files:
        raw_path = f"{RAW_PREFIX}/{date}/{filename}"
        clean_path = f"{CLEAN_PREFIX}/{date}/{filename}"
        try:
            logger.info(f"Processing file: {filename}")
            df = download_json_as_polars_blob(raw_path)
            if df is None:
                continue

            df_clean = run_cleaning_pipeline(df)
            upload_polars_to_gcs(df_clean, clean_path)
        except Exception as e:
            logger.exception(f"❌ Error processing file {filename}: {e}")

    logger.info(f"=== Finished cleaning for {date} ===")

if __name__ == "__main__":
    main("2025-03-29")  # 👈 replace or parameterize as needed
import logging
from google.cloud import bigquery, storage

# === Logging Setup ===
logger = logging.getLogger("bq_ndjson_loader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
file_handler = logging.FileHandler("logs/bq_ndjson_loader.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-row-434"
GCS_PREFIX = "clean-data-ndjson"
BQ_PROJECT = "hygiene-prediction-434"
BQ_DATASET = "HygienePredictionRow"
BQ_TABLE = "CleanedInspectionRow"

def load_ndjson_to_bigquery(date: str):
    storage_client = storage.Client()
    bq_client = bigquery.Client()

    folder = f"{GCS_PREFIX}/{date}/"
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=folder)

    for blob in blobs:
        if not blob.name.endswith(".ndjson"):
            continue

        gcs_uri = f"gs://{BUCKET_NAME}/{blob.name}"
        logger.info(f"Loading file into BigQuery: {gcs_uri}")

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
            load_job.result()  # Wait for completion
            logger.info(f"Loaded: {blob.name} into {table_id}")
        except Exception as e:
            logger.exception(f"Failed to load {blob.name}: {e}")

if __name__ == "__main__":
    load_ndjson_to_bigquery("2025-03-30")

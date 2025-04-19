import logging
from google.cloud import bigquery, storage
from google.auth import default

# === Logging Setup ===
logger = logging.getLogger("bq_parquet_loader")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s — %(levelname)s — %(message)s")
file_handler = logging.FileHandler("logs/bq_parquet_loader.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# === Constants ===
BUCKET_NAME = "cleaned-inspection-data-column"
GCS_PREFIX = "clean-data"
BQ_PROJECT = "hygiene-prediction"
BQ_DATASET = "HygienePredictionColumn"
BQ_TABLE = "CleanedInspectionColumn"

def ensure_dataset_exists(bq_client, dataset_id: str):
    try:
        bq_client.get_dataset(dataset_id)  # Will raise NotFound if not found
        logger.info(f"Dataset already exists: {dataset_id}")
        print(f"✅ Dataset found: {dataset_id}")
    except Exception as e:
        from google.cloud.exceptions import NotFound
        if isinstance(e, NotFound):
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = "US"
            bq_client.create_dataset(dataset)
            logger.info(f"Created dataset: {dataset_id}")
            print(f"🆕 Created dataset: {dataset_id}")
        else:
            logger.exception(f"Error checking or creating dataset: {dataset_id}")
            raise


def log_active_credentials():
    credentials, project = default()
    logger.info(f"Using ADC credentials for project: {project}")
    print(f"🔐 Using credentials for project: {project}")
    logger.info(f"Credentials type: {type(credentials)}")
    if hasattr(credentials, 'quota_project_id'):
        logger.info(f"Quota project ID: {credentials.quota_project_id}")

def load_parquet_to_bigquery(date: str):
    print(f"🚀 Starting BigQuery Parquet load for {date}...")
    storage_client = storage.Client()
    bq_client = bigquery.Client()
    dataset_id = f"{BQ_PROJECT}.{BQ_DATASET}"
    ensure_dataset_exists(bq_client, dataset_id)
  
    folder = f"{GCS_PREFIX}/{date}/"
    bucket = storage_client.bucket(BUCKET_NAME)
    blobs = bucket.list_blobs(prefix=folder)

    count = 0
    for blob in blobs:
        if not blob.name.endswith(".parquet"):
            continue

        gcs_uri = f"gs://{BUCKET_NAME}/{blob.name}"
        logger.info(f"Loading Parquet file into BigQuery: {gcs_uri}")
        print(f"⏳ Loading: {blob.name}")

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        table_id = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

        try:
            load_job = bq_client.load_table_from_uri(
                gcs_uri, table_id, job_config=job_config
            )
            load_job.result()
            logger.info(f"Loaded: {blob.name} into {table_id}")
            print(f"✅ Loaded: {blob.name}")
            count += 1
        except Exception as e:
            logger.exception(f"Failed to load {blob.name}: {e}")
            print(f"❌ ERROR loading {blob.name} — see log")

    print(f"🎉 BigQuery Parquet load complete: {count} file(s) processed.")

if __name__ == "__main__":
    log_active_credentials()
    load_parquet_to_bigquery("2025-03-30")

"""
Pipeline Monitor Dashboard
--------------------------

This Streamlit dashboard provides real-time observability for the hygiene prediction pipeline.
It monitors key pipeline components including:

- GCS buckets: file counts and last update timestamps
- BigQuery tables: row counts and last modified times
- Cloud Run services: dashboard and API availability status
- Trigger control: manual pipeline activation via /run
- Reset functions: clear GCS, truncate BQ tables, purge trigger cache

"""

import streamlit as st
import requests
from google.cloud import storage, bigquery
from datetime import datetime

st.set_page_config(page_title="Pipeline Monitor", layout="centered")
st.title("📊 Pipeline Activity Monitor")


# === PIPELINE SERVICE STATUS ===

st.header("⚙️ Pipeline Service Status")

PIPELINE_SERVICES = {
    "Extractor": "https://extractor-ppivhedgva-uc.a.run.app",
    "Cleaner": "https://cleaner-ppivhedgva-uc.a.run.app",
    "Loader-JSON": "https://loader-json-ppivhedgva-uc.a.run.app",
    "Loader-Parquet": "https://loader-parquet-ppivhedgva-uc.a.run.app",
    "Trigger": "https://trigger-ppivhedgva-uc.a.run.app",
    "EDA Dashboard": "https://eda-dashboard-ppivhedgva-uc.a.run.app",
    "ML Dashboard": "https://ml-dashboard-ppivhedgva-uc.a.run.app",
    "ML UI (hygiene-ml-ui)": "https://hygiene-ml-ui-ppivhedgva-uc.a.run.app",
    "Chicago Open Data API": "https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=1"
}

def check_service_status(url):
    health_url = url.rstrip("/") + "/health"
    try:
        response = requests.head(health_url, timeout=5)
        if response.status_code in (200, 405):
            return True
        # If HEAD fails (some Cloud Run containers reject it), try GET
        response = requests.get(health_url, timeout=5)
        return response.status_code in (200, 405)
    except:
        return False


for name, url in PIPELINE_SERVICES.items():
    is_up = check_service_status(url)
    status = "🟢 Alive" if is_up else "🔴 Unreachable"
    st.write(f"**{name}** → {status}")


# === GCS BUCKET SUMMARY ===

st.header("GCS Bucket Status")

GCS_BUCKETS = {
    "Raw Inspection Data": ("raw-inspection-data-434", "raw-data/"),
    "Cleaned Column Data": ("cleaned-inspection-data-column-434", "clean-data/"),
}


def get_blob_summary(bucket_name):
    client = storage.Client()
    blobs = list(client.list_blobs(bucket_name))
    count = len(blobs)
    updated = max([b.updated for b in blobs], default=None)
    return count, updated

for label, (bucket, _) in GCS_BUCKETS.items():
    try:
        count, latest = get_blob_summary(bucket)
        latest_fmt = latest.strftime("%Y-%m-%d %H:%M:%S") if latest else "N/A"
        st.write(f"**{label}**: {count:,} files (Last updated: {latest_fmt})")
    except Exception as e:
        st.error(f"Failed to fetch info for {label}: {e}")


# === BIGQUERY TABLE SUMMARY ===

st.header("BigQuery Table Status")

BQ_TABLES = {
    "Cleaned Inspection Data (Column)": "HygienePredictionColumn.CleanedInspectionColumn",
}

def get_table_info(dataset_table):
    client = bigquery.Client()
    table = client.get_table(dataset_table)
    return table.num_rows, table.modified

for label, full_table_id in BQ_TABLES.items():
    try:
        rows, modified = get_table_info(full_table_id)
        modified_fmt = modified.strftime("%Y-%m-%d %H:%M:%S")
        st.write(f"**{label}**: {rows:,} rows (Last modified: {modified_fmt})")
    except Exception as e:
        st.error(f"Failed to fetch info for {label}: {e}")

if "refresh" not in st.session_state:
    st.session_state.refresh = False

if st.button("🔄 Refresh File and Table Status"):
    st.session_state.refresh = not st.session_state.refresh
    
# === MANUAL PIPELINE TRIGGER ===

st.header("📤 Manually Trigger Pipeline")

with st.form("trigger_form"):
    date = st.text_input("Run date (YYYY-MM-DD)", value=str(datetime.today().date()))
    max_offset = st.number_input("Max offset (rows)", value=1000, step=100)

    st.markdown("### ⚙️ Simulation Settings")

    level_options = ["None", "Low", "Medium", "High"]
    level_map = {"None": 0.0, "Low": 0.01, "Medium": 0.05, "High": 0.15}

    api_level = st.selectbox("API Error Rate", level_options, index=1)
    gcs_level = st.selectbox("GCS Write Error Rate", level_options, index=2)
    drop_level = st.selectbox("Row Drop Rate", level_options, index=2)
    delay_level = st.selectbox("Delay Rate", level_options, index=2)
    
    
    st.markdown("#### Simulation Level Reference")
    st.table({
        "Level": ["None", "Low", "Medium", "High"],
        "Probability": [f"{level_map['None']:.2f}",
                        f"{level_map['Low']:.2f}",
                        f"{level_map['Medium']:.2f}",
                        f"{level_map['High']:.2f}"]
    })

 

    submitted = st.form_submit_button("🚀 Run Pipeline")




if submitted:
    trigger_url = "https://trigger-931515156181.us-central1.run.app/run"
    payload = {
        "date": date,
        "max_offset": int(max_offset),
        "api_error_prob": level_map[api_level],
        "gcs_error_prob": level_map[gcs_level],
        "row_drop_prob": level_map[drop_level],
        "delay_prob": level_map[delay_level]
    }
    st.markdown("#### Payload Preview")
    st.json(payload)
    
    try:
        response = requests.post(trigger_url, json=payload)
        if response.status_code == 200:
            st.success(f"✅ Pipeline triggered for {date} with max_offset={max_offset}")
        else:
            st.error(f"❌ Failed with status {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"🚨 Error: {e}")



# === RESET PIPELINE STATE ===

st.header("🧹 Reset Pipeline State")

def clear_gcs_bucket(bucket_name, prefix=""):
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        if blobs:
            bucket.delete_blobs(blobs)
            return True
        return False
    except Exception as e:
        st.error(f"❌ GCS error for bucket {bucket_name}: {e}")
        return False

if st.button("🗑 Clear GCS Buckets"):
    success = True
    for label, (bucket, prefix) in GCS_BUCKETS.items():
        if clear_gcs_bucket(bucket, prefix):
            st.success(f"✅ Cleared: {label}")
        else:
            st.warning(f"⚠️ No files to delete in {label} or failed.")

if st.button("🧽 Truncate BigQuery Tables"):
    try:
        client = bigquery.Client()
        # Truncate both tables
        client.query(
            "TRUNCATE TABLE `hygiene-prediction-434.HygienePredictionColumn.CleanedInspectionColumn`"
        ).result()
        client.query(
            "TRUNCATE TABLE `hygiene-prediction-434.PipelineMonitoring.chunk_metrics`"
        ).result()
        st.success("✅ Both BigQuery tables truncated.")
    except Exception as e:
        st.error(f"❌ Error truncating BigQuery tables: {e}")


if st.button("🧹 Purge Trigger Cache"):
    try:
        purge_url = "https://trigger-931515156181.us-central1.run.app/purge"
        response = requests.post(purge_url)
        if response.status_code == 200:
            st.success("✅ Trigger cache cleared.")
        else:
            st.error(f"❌ Failed with status {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"🚨 Error: {e}")

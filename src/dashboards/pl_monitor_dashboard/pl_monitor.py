import streamlit as st
import requests
from google.cloud import storage, bigquery
from datetime import datetime

st.set_page_config(page_title="Pipeline Monitor", layout="centered")
st.title("📊 Pipeline Activity Monitor")

# Add refresh button
if st.button("🔄 Refresh Now"):
    st.experimental_rerun()

# === GCS BUCKET SUMMARY ===
st.header("GCS Bucket Status")

GCS_BUCKETS = {
    "Raw Inspection Data": "raw-inspection-data-434",
    "Cleaned Row Data": "cleaned-inspection-data-row-434",
    "Cleaned Column Data": "cleaned-inspection-data-column-434",
}

def get_blob_summary(bucket_name):
    client = storage.Client()
    blobs = list(client.list_blobs(bucket_name))
    count = len(blobs)
    updated = max([b.updated for b in blobs], default=None)
    return count, updated

for label, bucket in GCS_BUCKETS.items():
    try:
        count, latest = get_blob_summary(bucket)
        latest_fmt = latest.strftime("%Y-%m-%d %H:%M:%S") if latest else "N/A"
        st.write(f"**{label}**: {count:,} files (Last updated: {latest_fmt})")
    except Exception as e:
        st.error(f"Failed to fetch info for {label}: {e}")

# === BIGQUERY TABLE SUMMARY ===
st.header("BigQuery Table Status")

BQ_TABLES = {
    "Cleaned Inspection Data (Row)": "HygienePredictionRow.CleanedInspectionRow",
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

# === MANUAL PIPELINE TRIGGER ===
st.header("📤 Manually Trigger Pipeline")

with st.form("trigger_form"):
    date = st.text_input("Run date (YYYY-MM-DD)", value=str(datetime.today().date()))
    max_offset = st.number_input("Max offset (rows)", value=1000, step=100)
    submitted = st.form_submit_button("🚀 Run Pipeline")

if submitted:
    trigger_url = "https://trigger-931515156181.us-central1.run.app/run "  # Replace with your actual trigger URL
    payload = {"date": date, "max_offset": int(max_offset)}
    try:
        response = requests.post(trigger_url, json=payload)
        if response.status_code == 200:
            st.success(f"✅ Pipeline triggered for {date} with max_offset={max_offset}")
        else:
            st.error(f"❌ Failed with status {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"🚨 Error: {e}")
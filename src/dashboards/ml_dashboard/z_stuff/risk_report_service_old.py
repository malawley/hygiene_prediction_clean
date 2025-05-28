from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse
from google.cloud import storage
import tempfile
import os
import sys
import traceback
import time

# === Set up Google Cloud credentials (default or overridden via env) ===
key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/hygiene-key.json")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# ✅ Import the pipeline entry point
from risk_report_generator import pull_and_score

# === Initialize FastAPI ===
app = FastAPI()

class ReportRequest(BaseModel):
    inspector_id: str
    month_year_tag: str
    n: int
    top_n: int
    seed: int

@app.post("/generate_report")
async def generate_report(request: Request):
    print("📥 FastAPI endpoint was hit!")

    try:
        body = await request.json()
        print("📦 Parsed JSON body:", body)

        # Extract fields safely
        inspector_id = body.get("inspector_id")
        month_year_tag = body.get("month_year_tag")
        n = int(body.get("n", 30))
        top_n = int(body.get("top_n", 50))
        seed = int(body.get("seed", 42))

        # Run your pipeline
        df = pull_and_score(inspector_id, month_year_tag, n, top_n, seed)

        # Write CSV to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline='') as tmpfile:
            df.to_csv(tmpfile.name, index=False)
            output_path = tmpfile.name

        # Pause to ensure file system sync
        time.sleep(0.5)

        # Confirm file exists and is non-empty
        print(f"✅ File written: {output_path}")
        print(f"📏 File size: {os.path.getsize(output_path)} bytes")

        # Define output filename for GCS
        gcs_filename = f"risk_report_{inspector_id}_{month_year_tag}_top{top_n}.csv"

        # Upload to GCS and generate signed download URL
        signed_url = upload_and_get_signed_url(
            bucket_name="restaurant-risk-reports",
            local_file_path=output_path,
            destination_blob_name=gcs_filename
        )

        # Clean up local file
        os.remove(output_path)

        print(f"🔗 Signed URL generated: {signed_url}")
        # Return signed URL to Streamlit
        return {
            "status": "success",
            "download_url": signed_url
        }

    except Exception as e:
        print("🔥 Exception in FastAPI handler:")
        traceback.print_exc()
        return {"detail": str(e)}
    
    
from datetime import timedelta
from google.cloud import storage

def upload_and_get_signed_url(bucket_name: str, local_file_path: str, destination_blob_name: str, expiration_minutes: int = 15) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Upload file to GCS
    blob.upload_from_filename(local_file_path)

    # Generate signed URL (v4)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET"
    )

    return url
    
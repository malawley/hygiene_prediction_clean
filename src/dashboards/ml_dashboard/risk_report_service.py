from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from google.cloud import storage
from datetime import timedelta
import os
import sys
import traceback
from dotenv import load_dotenv
load_dotenv()



# === Import your GCS-native risk report generator ===
from risk_report_generator import generate_inspection_report

# === Initialize FastAPI app ===
app = FastAPI()


class ReportRequest(BaseModel):
    inspector_id: int
    n: int
    seed: int


@app.post("/generate_report")
async def generate_report(request: Request):
    print("📥 FastAPI endpoint was hit!")

    try:
        body = await request.json()
        print("📦 Parsed JSON body:", body)

        # Extract fields
        inspector_id = int(body.get("inspector_id"))
        sample_size = int(body.get("n", 30))
        seed = int(body.get("seed", 42))

        # Run the pipeline
        df, gcs_uri = generate_inspection_report(
            inspector_id=inspector_id,
            seed=seed,
            sample_size=sample_size
        )

        # Extract GCS filename
        gcs_filename = gcs_uri.split("/")[-1]

        # Generate signed URL
        signed_url = generate_signed_url(
            bucket_name="restaurant-risk-reports",
            blob_name=gcs_filename,
            expiration_minutes=15
        )

        print(f"✅ Signed URL: {signed_url}")
        return {
            "status": "success",
            "download_url": signed_url
        }

    except Exception as e:
        print("🔥 Exception in FastAPI handler:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# === Signed URL Generator ===
def generate_signed_url(bucket_name: str, blob_name: str, expiration_minutes: int = 15) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiration_minutes),
        method="GET"
    )

    return url

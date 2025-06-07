# 🔧 Hygiene Prediction Pipeline - Demo User Guide

This guide explains how to interact with the live dashboards hosted on Google Cloud Run for the hygiene prediction pipeline. No cloning or setup is required. These dashboards allow users to trigger the pipeline, monitor services, explore data, and view model results in real time.

There are three dashbords
- Pipeline Controller Dashboard  - Starts backend microservices that extract, clean, and load data, URL: https://pipeline-monitor-931515156181.us-central1.run.app
- EDA Dashboard Preview - Supports Explorator Data Analysis of cleaned and loaded data,  URL: https://eda-dashboard-931515156181.us-central1.run.app/
- ML Model Performance Dashboard - Provides performance metrics of machine learning models and generates inspection reports for decision support, URL: https://hygiene-ml-ui-931515156181.us-central1.run.app/


## 📊 Pipeline Controller Dashboard (Trigger UI)

URL: https://pipeline-monitor-931515156181.us-central1.run.app


This dashboard serves as the control center for the pipeline. It allows users to:

✅ **What You Can Do**

- View the status of all pipeline microservices (Extractor, Cleaner, Loaders, etc.)
- Monitor file and row counts in GCS buckets and BigQuery tables
- Trigger the entire pipeline manually for a specific date and row count
- Inject simulated pipeline unreliability (API errors, GCS write errors, row drops, delays)
- Reset pipeline state: clear GCS buckets, truncate BigQuery tables, purge trigger cache



🚀 **How to Use**

- **Check Service Status**
  - Green = alive, Red = unreachable

- **View Current Storage State**
  - GCS file counts and BQ table row counts are displayed

- **Trigger the Pipeline**
  - Enter a run date (format: YYYY-MM-DD)
  - Enter the max number of rows to extract
  - Use dropdowns to apply error rates (e.g., Low = 0.01, High = 0.15)
  - Click **Run Pipeline**
  - Wait for success or error response
  - Click on the manual refresh button every 8–10 seconds
  - Every 1000 rows will be saved as one file in the buckets
  - For 10,000 rows, expect ~10–12 files in GCS, depending on error rates
    

🧹 **Reset the Pipeline (Optional)**

- **Clear GCS Buckets**: Deletes all data files from raw/clean buckets
- **Truncate BigQuery**: Removes all rows from target BQ tables
- **Purge Trigger Cache**: Clears internal pipeline state stored by the trigger

<br>

📝 **Notes**

- This dashboard interacts with the actual deployed microservices using HTTP requests
- As the pipeline runs, files will be added to the GCS buckets and BigQuery table
- Make sure all services are online before triggering
- Expect delays for longer data loads or if error simulation is enabled
- Additional dashboards (EDA, ML results) will be added in subsequent sections

<br><br>

<br>
<br>

<br><br>


## 📊 EDA Dashboard Preview
<br>
URL: https://eda-dashboard-931515156181.us-central1.run.app/

This dashboard provides interactive visual analysis of food code violations in Chicago. Key features include:

- Top violation codes by count
- Breakdown by facility category
- Co-occurrence heatmap of violations
- Violation trends over time
- Zip code and geographic mapping

<br><br>

            
## 🤖 ML Model Performance Dashboard

URL: https://hygiene-ml-ui-931515156181.us-central1.run.app/

This dashboard supports interactive exploration of the hygiene risk scoring model and allows users to generate on-demand restaurant risk reports using a deployed ensemble classifier.

<br>

### 🧭 Navigation Overview

The sidebar offers two main sections:

- **🖼️ ML Summary** – Visual walkthrough of model architecture, performance, and interpretability
- **📊 Generate Risk Report** – Interactive form to request risk predictions on a random sample of inspections

<br>

### 🖼️ ML Summary Section

This section presents visual summaries of the deployed ML model:

- **Dashboard Landing** – Visual introduction to the risk scoring UI
- **Two-Stage Classification Flowchart** – Architecture overview of the ensemble approach
- **Confusion Matrix & ROC Curve** – Model performance at-a-glance
- **Feature Importance** – Bar plots of global model explanations
- **SHAP Summary Plot** – SHAP values for the XGBoost model
- **Tiered Decision Logic** – Precision-recall outcomes by decision tier
- **TP/FP Confusion Breakdown** – Error analysis across groups
- **Decision Tree** – Visual guide for the rule-based downstream classifier

📎 *Some figures are scaled to 50% for readability*


<br>


### 📊 Generate Risk Report Section

Use the form to simulate a restaurant inspection review session for a selected inspector.
<br>
#### 🔧 Inputs

- **Inspector ID** – Integer ID of the inspector (e.g., `23`)
- **Number of Inspections to Evaluate** – Size of the random sample (10 to 1000)
- **Random Seed** – Seed value to ensure repeatability of sampling
<br>
#### 🚀 Steps to Generate

1. Fill out all fields in the form  
2. Click **🚀 Generate Report**
3. Wait for the backend to process the request
4. Upon success, a download link will appear

<br>
#### 📝 Notes

- Backend is expected to be hosted at `/generate_report`
- Response must contain a signed GCS download URL
- CSV contains scored inspections with metadata and risk class

<br>

### 📥 Example Output

The downloadable CSV includes:

- `inspection_id`, `facility_name`, `risk_score`, `risk_class`
- Model features used for prediction
- Optional metadata (inspector ID, prediction timestamp)

<br>

### 🧪 Backend Requirements

This frontend sends a POST request to the backend service at:

```http
POST http://127.0.0.1:8090/generate_report
Content-Type: application/json

{
  "inspector_id": 23,
  "n": 100,
  "seed": 42
}
```

Make sure the backend microservice is deployed and reachable from the frontend for the report generation to work.

<br>
<br>


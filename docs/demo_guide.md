# 🔧 Hygiene Prediction Pipeline - Demo User Guide

This guide explains how to interact with the live dashboards hosted on Google Cloud Run for the hygiene prediction pipeline. No cloning or setup is required. These dashboards allow users to trigger the pipeline, monitor services, explore data, and view model results in real time.

There are four dashbords
- Pipeline Controller Dashboard  - Starts backend microservices that extract, clean, and load data, URL: https://pipeline-monitor-931515156181.us-central1.run.app
- Pipeline Chunk Metrics Dashboard - Monitors performance metrics of backend microservices, URL: http://localhost:3000/
- EDA Dashboard Preview - Supports Explorator Data Analysis of cleaned and loaded data,  URL: https://eda-dashboard-931515156181.us-central1.run.app/
- ML Model Performance Dashboard - Provides performance metrics of machine learning models and generates inspection reports for decision support, URL: https://hygiene-ml-ui-931515156181.us-central1.run.app/

Also, at the end of the document, there are instructions from running CI/CD on the microservice that loads parquet data into BigQuery. 

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



## 📊 Pipeline Chunk Metrics Dashboard (Grafana)

URL: http://localhost:3000/

This dashboard runs in a local Grafana container and monitors the **extractor microservice** during pipeline operation.

It displays key performance and fault indicators across each chunk of extracted data.

<br>

### 📈 Metrics Reported

The following Prometheus metrics are exposed by the extractor service:

- **extractor_requests_total**  
  ➤ Total number of **/extract** requests received

- **extractor_rows_fetched_total**  
  ➤ Total number of rows fetched from the Chicago inspections API

- **extractor_rows_dropped_total**  
  ➤ Total number of rows dropped during extraction

- **extractor_write_failures_total**  
  ➤ Number of failed attempts to write data to the raw GCS bucket

- **extractor_api_failures_total**  
  ➤ Number of failed HTTP calls to the Chicago API

- **extractor_last_run_duration_seconds**  
  ➤ Duration of the most recent extraction run (in seconds)

- **extractor_chunk_duration_seconds**  
  ➤ Duration of each 1000-row chunk, recorded individually

📌 _Each x-axis label in the dashboard corresponds to a chunk offset or timestamp (typically every 1000 rows)._  
🟥 Red bars in the dashboard highlight delays exceeding 20 seconds in **extractor_chunk_duration_seconds**.




<br>

### 🛠️ How to Run the Grafana Chunk Metrics Dashboard Locally

This section explains how to clone the pipeline project, set up the necessary credentials, and launch the local Grafana container with the BigQuery plugin to view extractor performance metrics.

---

#### 📅 Step 1: Clone the Project from GitHub

Download the full pipeline project from the GitHub repository:

```bash
git clone https://github.com/malawley/hygiene_prediction_clean.git
cd hygiene_prediction
```

This repository includes all Dockerfiles, microservice source code, configuration files, and dashboards.

---

#### 🔑 Step 2: Add a Service Account Key File

You will need a GCP service account key file with the following roles:

* BigQuery Data Viewer
* BigQuery Job User

Save the key as a `.json` file inside the root of the project directory. Grafana will load this key manually during setup.

---

#### 📦 Step 3: Install the BigQuery Plugin (first-time only)

Grafana requires the community BigQuery plugin to query GCP data. Run the following to install it inside the container:

```bash
docker run --rm \
  -v grafana-storage:/var/lib/grafana \
  grafana/grafana \
  grafana-cli plugins install grafana-bigquery-datasource
```

📝 This creates a persistent volume `grafana-storage` where the plugin will be cached.

---

#### ▶️ Step 4: Start the Grafana Container

Now launch Grafana, mounting the provisioning config and dashboards:

```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  --network pipeline-net \
  -v $PWD/monitoring/grafana:/etc/grafana/provisioning \
  -v grafana-storage:/var/lib/grafana \
  grafana/grafana
```

Grafana will be accessible at [http://localhost:3000](http://localhost:3000).

---

#### 🧐 Step 5: Configure the BigQuery Data Source

1. Open Grafana in your browser: [http://localhost:3000](http://localhost:3000)
2. Log in (default user/password is `admin` / `admin`)
3. Go to **Connections → Data Sources**
4. Click **Add Data Source → BigQuery**
5. Upload the service account JSON key
6. Set the project ID to `hygiene-prediction-434`
7. Click **Save & Test**

✅ You should see a green “Data source is working” message.

---

#### 📈 Step 6: Open the Chunk Metrics Dashboard

1. Go to **Dashboards → Browse**
2. Select the dashboard titled:
   👉 **Project Pipeline Chunk Metrics Dashboard**
3. Click **Refresh** (top right) to load the latest chunk metrics

Each panel displays time-filtered data extracted from the BigQuery table:

```
hygiene-prediction-434.PipelineMonitoring.chunk_metrics
```

📅 Ensure that the time range is set to **“Last 24 hours”** or **“Last 30 days”** depending on your testing window.



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

## ✅ Continuous Deployment: `loader-parquet` (via GitHub Actions)

The `loader-parquet` microservice is deployed automatically using a GitHub Actions workflow defined in `deploy-loader-parquet.yml`.

Any time you push a commit that changes this service, GitHub Actions will:

1. Build a new Docker image from `src/loader/parquet/Dockerfile`
2. Push the image to Google Artifact Registry
3. Deploy the image to Cloud Run under the service name `loader-parquet`

---

### 🚀 How to Trigger a Redeploy

Make a harmless change to the loader script (e.g., add a comment):

```bash
echo "# Trigger redeploy for demo" >> src/loader/parquet/bq_parquet_loader.py

git add src/loader/parquet/bq_parquet_loader.py
git commit -m "🚀 Trigger redeploy of loader-parquet for demo"
git push origin main

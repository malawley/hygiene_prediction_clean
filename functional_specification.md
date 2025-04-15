**Functional Specification: Cloud-Native Pipeline for Predicting Chicago Food Code Violations**

**Project Overview**
This project is a fully cloud-native machine learning pipeline hosted on Google Cloud Platform (GCP). It aims to extract, clean, transform, analyze, and model food inspection data from the City of Chicago's Open Data Portal to predict likely code violations. The pipeline is containerized, modular, and orchestrated through Cloud Run and supporting GCP services. A Streamlit dashboard provides interactive data exploration and model result visualizations.

**Functional Components**

1. **Data Extraction (Extractor Service)**
   - Fetches raw inspection data via the City of Chicago API in chunks.
   - Stores raw JSON files in a Google Cloud Storage (GCS) bucket.
   - Writes a manifest file with a list of extracted files and completion status.
   - Exposes an HTTP endpoint to be triggered by Cloud Scheduler.
   - Triggers the Cleaner service via HTTP POST upon successful completion.

2. **Data Cleaning (Cleaner Service)**
   - Triggered via HTTP with the processing date as a parameter.
   - Loads raw data from GCS using the manifest.
   - Applies a multi-stage cleaning pipeline using Polars.
   - Writes cleaned outputs to separate row-oriented (NDJSON) and column-oriented (Parquet) GCS buckets.
   - Writes manifest files for both outputs.
   - Triggers both BigQuery loader services.

3. **Data Loading (Loader Services)**
   - **NDJSON Loader**: Loads row-oriented NDJSON data from GCS to BigQuery, supporting data exploration and intermediate analytics.
   - **Parquet Loader**: Loads column-oriented Parquet data from GCS to BigQuery, optimized for dashboard queries and machine learning workflows.
   - Both services read manifests to determine which files to load for a given processing date.
   - Each exposes an HTTP endpoint to support chained or scheduled execution.

4. **EDA Dashboard (Streamlit App)**
   - Hosted on Cloud Run or GCE.
   - Connects to BigQuery to retrieve processed data and insights.
   - Provides multiple tabs:
     - Top Violations Overview
     - Violation by Facility Category
     - Violation Co-occurrence Heatmap
     - Choropleth by ZIP Code
     - Violation Trends Over Time
     - Facility Map of Violations

5. **Machine Learning (In Progress)**
   - Will use cleaned and labeled data to train supervised models for predicting food code violations.
   - Training code will be written as a standalone Python script and containerized for reproducibility and deployment.
   - The training container can be executed manually, on a schedule, or as part of an automated pipeline.
   - Model outputs will be written back to BigQuery.
   - Performance metrics and predictions will be integrated into the Streamlit dashboard.

6. **Metadata Dashboard (Planned)**
   - Aims to show data freshness, pipeline execution stats, file counts, and BigQuery table metrics.
   - Will help monitor the health and recency of the pipeline.



**Technology Stack**
- **GCP Services**: Cloud Run, Cloud Storage, BigQuery, Cloud Scheduler, IAM, Artifact Registry
- **Languages**: Go (extractor), Python (cleaner, loaders, Streamlit)
- **Libraries**: Polars, pandas, Flask, Plotly, Seaborn, Streamlit, google-cloud SDKs
- **DevOps**: Docker, Git, Cloud Build

**Execution and Coordination**
- Cloud Scheduler triggers the Extractor daily.
- Extractor triggers Cleaner via HTTP upon writing manifest.
- Cleaner triggers both Loaders via HTTP.
- All services are stateless and coordinated using GCS manifests and HTTP calls.

**Cloud-Native Considerations**
- All logic is deployed in containers and run from Cloud Run.
- No persistent local state is required.
- Credentials are handled via IAM roles and Application Default Credentials.
- All coordination and state handoff use durable cloud-native services (GCS, BigQuery).

**Version Control**
- All code is version-controlled in Git and structured for modular deployment.
- Dockerfiles and deployment scripts are maintained in each microservice directory.

**PaaS vs Cloud-Native Discussion**
- This project intentionally avoids PaaS (like App Engine or Beanstalk) in favor of containerized Cloud Run deployments.
- Benefits of Cloud Run:
  - Language-agnostic
  - Fully managed but flexible
  - Pay-per-use and scalable
  - Compatible with Git-based CI/CD
- Compared to PaaS, Cloud Run allows precise control over execution flow, integration with GCS-based coordination, and separation of concerns.

**Future Improvements**
- Add CI/CD pipelines for automated testing and deployment.
- Use Cloud Workflows for orchestration if needed.
- Add support for reprocessing historical data in batches.
- Optimize performance and concurrency for large data pulls.
- Extend the Streamlit dashboard with model explanations and interactive prediction interfaces.


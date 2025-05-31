# Project: Chicago Restaurant Health Inspection Machine Learning Pipeline 

This project develops an end to end machine learning pipeline based on the Chicago Open Portal Food Inspection Database. The use case for the pipeline is as follows:  

A public health inspector has completed an inspection of a restaurant and has to decide whether it should be a pass, pass with condition, or fail. The decision needs to be consistent with general historical practice. The inspector needs a decision support tool that accepts data collected from the on-site inspection and makes a recommendation about pass, pass with condition, or fail that is consistent with historical inspection decisions. 

To support this use case, a cloud-native machine learning pipeline that collects, cleans, transforms, and stores data, supports exploratory data analysis, machine learning training and prediction, and inspection report generation has been created. The design architecture is a containerized set of microservices implemented in the Google Cloud Platform.

> 📘 **Looking for the walkthrough?**  
> Check out the full [Demo Usage Guide](docs/demo_guide.md) to run the pipeline, view dashboards, and test CI/CD.


---

## 📆 Project Overview

* **Use Case:** Food safety inspection prioritization
* **Domain:** Public Health, Cloud Data Engineering, ML Ops
* **Pipeline Layers:**

  * Data extraction from Chicago Open Data API
  * Cleaning and validation
  * Loading into BigQuery (Parquet + JSONL formats)
  * Machine learning model training and prediction
  * Dashboarding and risk score reporting
* **Deployment Target:** Google Cloud Platform (GCP)

---

## ⚙️ Technologies Used

* **Languages:** Python, Go
* **Cloud:** Google Cloud Run, BigQuery, Cloud Storage
* **CI/CD:** GitHub Actions, Docker
* **Monitoring:** Prometheus + Grafana
* **Orchestration:** Trigger microservice (Go)
* **UI:** Streamlit dashboards for control and reporting

---

## 📁 Microservice Structure

```
hygiene_prediction_clean/
├── src/
│   ├── extractor/         # Go service to pull API data to GCS
│   ├── cleaner/           # Python service to clean and standardize data
│   ├── loader/json/       # Python loader to ingest NDJSON into BigQuery (row-level)
│   ├── loader/parquet/    # Python loader to ingest Parquet into BigQuery (columnar)
│   ├── trigger/           # Go-based service to orchestrate pipeline steps
│   └── dashboards/        # Streamlit-based EDA + ML dashboards
├── docs/                  # Design documentation, PDFs, specs
├── .github/workflows/     # GitHub Actions deployment configs
├── Makefile               # Task automation (build, deploy, clean)
└── video_links.md         # Weekly Panopto demo recordings
```

---


### 👥 For Users / Reviewers

This is a fully deployed, cloud-native system. You **do not need to clone the repository** to interact with it.

> 📘 **See the Live Demo Guide:**  
> Use the [Demo Usage Guide](docs/demo_guide.md) to:
> - Trigger the pipeline
> - View dashboards
> - Monitor system health
> - Test error injection
> - Confirm CI/CD redeployments (this requires cloning and setup)

---

## 📼 Project Demo Videos

Full video documentation of each project stage is available in [`video_links.md`](video_links.md).

---

## 📄 License

MIT License — see `LICENSE` file for details.

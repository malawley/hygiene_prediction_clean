# ✅ Cloud Run Deployment Workflow for a Containerized Microservice System

This document outlines the full end-to-end process for developing, containerizing, configuring, and deploying a microservice-based system on **Google Cloud Run**, using **Artifact Registry** for image storage. It includes executive-level summaries, detailed steps, and a troubleshooting appendix.

---

## 🌐 Executive Overview

Containerized microservices must be adapted for the cloud environment in order to operate as a cohesive, scalable system. Google Cloud Run provides a managed compute platform that abstracts away infrastructure concerns. Each microservice becomes an independent web service with a dedicated HTTPS endpoint. To coordinate communication, configuration must be externalized, authentication scoped correctly, and communication links reestablished with secure URLs.

The deployment workflow therefore includes: local development and testing, cloud container registry setup, container image tagging and push, Cloud Run service creation, environment variable configuration for secure inter-service communication, and IAM permission setup.

---

## 🚧 Step-by-Step Workflow

### **1. Develop and Test Locally**

- Build each service (e.g., extractor, cleaner, dashboard) as a **Docker container**.
- Use **Docker Compose** to simulate the full system locally.
- Test all endpoints and ensure inter-service URLs use container names (e.g., `http://trigger:8080/clean`).

### **2. Prepare Dockerfiles**

- Each microservice has its own `Dockerfile`.
- Include dependencies, port exposure, entry point (CMD), and environment configuration.
- Use minimal base images (e.g., `python:3.11-slim`, `distroless`) for security.

### **3. Authenticate Docker with Google Cloud**

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

- This writes credential helpers into `~/.docker/config.json`.
- Ensures Docker can push to Artifact Registry.

### **4. Tag Images for Artifact Registry**

```bash
docker tag local_image_name us-central1-docker.pkg.dev/PROJECT_ID/REPOSITORY_NAME/IMAGE_NAME
```

Example:
```bash
docker tag hygiene_prediction-trigger us-central1-docker.pkg.dev/hygiene-prediction/containers/trigger
```

### **5. Push Images to Artifact Registry**

```bash
docker push us-central1-docker.pkg.dev/hygiene-prediction/containers/trigger
```

- Repeat for all images.
- Validate with `gcloud artifacts repositories list` and `gcloud auth list`.

### **6. Deploy to Cloud Run**

```bash
gcloud run deploy SERVICE_NAME \
  --image=us-central1-docker.pkg.dev/PROJECT_ID/REPOSITORY/IMAGE_NAME \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated
```

Example:
```bash
gcloud run deploy trigger \
  --image=us-central1-docker.pkg.dev/hygiene-prediction/containers/trigger \
  --allow-unauthenticated
```

- Configure additional settings like memory, CPU, concurrency, environment variables.

### **7. Configure Inter-Service Communication**

#### Executive Summary:
Cloud Run assigns each service its own **HTTPS URL**. These URLs must be shared among services for communication. Environment variables or config files (e.g., `services.json`) are updated with Cloud Run endpoints. Communication is secured via HTTPS.

**Example configuration:**
```json
{
  "trigger": { "url": "https://trigger-abc123.run.app" },
  "cleaner": { "url": "https://cleaner-xyz456.run.app" }
}
```

- Replace Docker hostnames with public URLs.
- Use `gcloud run services list` to get the deployed URLs.

### **8. Set IAM Permissions**

- Grant services the correct access:
```bash
gcloud projects add-iam-policy-binding hygiene-prediction \
  --member="user:YOUR_EMAIL" \
  --role="roles/artifactregistry.writer"
```

- Grant service accounts roles like:
  - `roles/run.invoker` for calling services
  - `roles/bigquery.user` or `roles/bigquery.jobUser`
  - `roles/storage.objectViewer`

### **9. Monitor and Debug**

- Use Cloud Logging:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=trigger" --limit=50
```
- Verify network requests, environment variables, and IAM access.

### **10. (Optional) Automate with CI/CD**

- Use Cloud Build or GitHub Actions:
  - Build Docker image
  - Push to Artifact Registry
  - Deploy to Cloud Run

---

## 🧠 Key Concepts Summary

| Concept | Description |
|--------|-------------|
| **Cloud Run** | Deploys stateless containers with HTTPS endpoints |
| **Artifact Registry** | Secure image repository scoped to GCP projects |
| **Service-to-Service** | Configured using full URLs and secure IAM authentication |
| **Environment Variables** | Used to inject endpoint locations, auth settings, or config into containers |
| **IAM Roles** | Allow or restrict container access to BigQuery, Storage, etc. |
| **Monitoring** | Done via `gcloud logging` and Cloud Console for each Cloud Run service |

---

## 🧠 Appendix: Why Design for Cloud-Native from the Start

### ✅ Why Cloud-Native From the Start Is Often Better

1. **Local and cloud have fundamentally different assumptions**

| Concern         | Docker Compose                     | Cloud Run / Native Cloud          |
|----------------|------------------------------------|----------------------------------|
| Networking      | Shared DNS, localhost, ports       | Public HTTPS URLs, no shared DNS |
| Discovery       | Hardcoded service names            | Dynamic service URLs             |
| Secrets         | Files or `.env` files              | Secret Manager, env vars         |
| Lifecycle       | Always-on containers               | On-demand, auto-shutdown         |
| Logging         | Local log files                    | Cloud Logging (stdout)           |

2. **Cloud-native encourages composability and discipline**
- Stateless containers
- Config via environment variables
- Decoupled via HTTP/pub-sub triggers
- Structured logging to Cloud Logging
- Repeatable deployment automation (e.g., `cloud_deploy.py`)

3. **Infrastructure becomes your platform**
- GCS replaces local file storage
- BigQuery replaces local databases
- Cloud Run replaces Compose orchestration
- Cloud Logging replaces `tail` and local files

### ⚖️ When Local-First Might Still Make Sense
- Prototyping or teaching without cloud credentials
- Known hybrid or on-prem targets

🧠 **Final Thought:**
> If your destination is the cloud, design for the cloud from day one.

---

## 📦 Appendix: How Docker Compose and Cloud Run Differ for Service Discovery

### 🔍 Why You Needed `services.json`
Each service needs to know how to reach others. You used `services.json` to centralize the internal URLs.

```json
{
  "trigger": { "url": "http://trigger:8080/clean" },
  "cleaner": { "url": "http://cleaner:8080/clean" }
}
```

### 🐳 Docker Compose: Internal DNS
- Services share a private network and resolve each other via name (`trigger`, `cleaner`)
- You mount `services.json` or bake it into the container
- Services can use `http://trigger:8080/clean`

### ☁️ Cloud Run: Public URLs, No Internal DNS
- Each service is public and isolated
- No shared DNS — must use real HTTPS URLs
- You use `gcloud run services describe` to fetch live URLs
- These are injected via `SERVICE_CONFIG_B64`

```json
{
  "trigger": { "url": "https://trigger-abc123.run.app/clean" },
  "cleaner": { "url": "https://cleaner-xyz456.run.app/clean" }
}
```

### ✅ How You Solved It
- Built a dynamic `services.json`
- Base64-encoded it into `SERVICE_CONFIG_B64`
- Injected it as an environment variable
- Each container decodes and uses it at runtime

| Mode           | Do you need `services.json`?        | Why / Why Not                                             |
|----------------|--------------------------------------|-----------------------------------------------------------|
| Docker Compose | ✅ Yes — built or mounted             | Needed to resolve DNS-based service names                 |
| Cloud Run      | ❌ Not as a file — use base64 env var | URLs are dynamic and must be passed after deploy          |

🧠 This pattern is clean, stateless, and cloud-native. It’s a pattern worth teaching.

---

## 🛠 Troubleshooting Appendix

### ❌ `403 Forbidden` on `docker push`
**Cause:** Docker not authenticated.
**Fix:**
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```
Ensure proper IAM permissions: `roles/artifactregistry.writer`

### ❌ `Failed to decode JSON` in Go service
**Cause:** Go expects string fields, but numbers are passed.
**Fix:** Ensure payload values are strings. Use `fmt.Sprintf("%d", number)` when marshaling in Go.

### ❌ Cannot access `/logs` directory in container
**Cause:** Volume mount conflict or missing `MkdirAll()` in Go.
**Fix:** Ensure `os.MkdirAll("/logs", 0755)` and volume is mounted in Docker Compose and Cloud Run.

### ❌ Duplicate events triggered twice
**Cause:** Service retry logic or parallel triggers.
**Fix:** Implement deduplication tracking (e.g., in-memory or DB) inside the trigger service.

### ❌ BigQuery fails in Cloud Run
**Cause:** Service account lacks permission.
**Fix:** Assign `roles/bigquery.user` or `roles/bigquery.jobUser` to the Cloud Run service account.

### ❌ Streamlit UI error: `Permission denied: credentials file`  
**Cause:** Service account file not mounted.
**Fix:** Add `GOOGLE_APPLICATION_CREDENTIALS` env var and mount `.json` key file in Docker or Cloud Run deployment.

---

## ✅ Final Thoughts
This reference guide captures all key operational steps required to containerize, configure, deploy, and connect a multi-service system using Google Cloud Run. Keep it updated with lessons learned from production deployment. Also consider moving towards automated CI/CD and infrastructure-as-code for long-term scalability.

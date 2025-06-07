# === Microservices Pipeline Makefile ===
# USAGE EXAMPLES:
#   make build             → Clean everything, rebuild, and start fresh
#   make extract 5000      → Trigger pipeline with 5000 rows (default today)
#   make tail cleaner      → Tail logs from a specific container
#   make stop loader-json  → Stop just one container
#   make gcs-clear         → Clear all GCS buckets used in the pipeline
#   make bq-clear          → Truncate BigQuery tables

# === DEFAULTS ===
DATE ?= $(shell date +%F)
MAX ?= 1000

# === MANUAL BUILD TARGETS FOR CLOUD RUN SERVICES ===

build-extractor:
	docker build -t hygiene_prediction-extractor ./src/extractor

build-cleaner:
	docker build -t hygiene_prediction-cleaner ./src/cleaner

build-loader-json:
	docker build -t hygiene_prediction-loader-json ./src/loader-json

build-loader-parquet:
	docker build -t hygiene_prediction-loader-parquet ./src/loader-parquet

build-trigger:
	@echo "🔨 Building trigger binary..."
	cd ./src/trigger && go build -o build/trigger ./cmd/trigger.go
	@echo "🐳 Building Docker image..."
	docker build -t hygiene_prediction-trigger ./src/trigger


# === FULL BUILD, TAG, PUSH, DEPLOY FOR EACH SERVICE ===
# ===  Make Commands above are not needed

deploy-extractor:
	@echo "🐳 Building Docker image for extractor..."
	docker build --no-cache -t hygiene_prediction-extractor -f ./src/extractor/Dockerfile ./src/extractor

	@echo "🔐 Authenticating with Artifact Registry..."
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev

	@echo "📦 Tagging and pushing image to Artifact Registry..."
	docker tag hygiene_prediction-extractor us-central1-docker.pkg.dev/hygiene-prediction-434/containers/extractor
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/extractor

	@echo "🚀 Deploying to Cloud Run..."
	gcloud run deploy extractor \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/extractor \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300 \
	  --set-env-vars=BUCKET_NAME=raw-inspection-data-434,TRIGGER_URL=https://trigger-931515156181.us-central1.run.app/clean



deploy-cleaner:
	docker build -t hygiene_prediction-cleaner ./src/cleaner
	docker tag hygiene_prediction-cleaner us-central1-docker.pkg.dev/hygiene-prediction-434/containers/cleaner
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/cleaner
	gcloud run deploy cleaner \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/cleaner \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300 \
	  --set-env-vars=RAW_BUCKET=raw-inspection-data-434,CLEAN_BUCKET_ROW=cleaned-inspection-data-row-434,CLEAN_BUCKET_COLUMN=cleaned-inspection-data-column-434,TRIGGER_URL=https://trigger-931515156181.us-central1.run.app/clean


deploy-loader-json:
	docker build -t hygiene_prediction-loader-json ./src/loader-json
	docker tag hygiene_prediction-loader-json us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-json
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-json
	gcloud run deploy loader-json \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-json \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300 \
	  --set-env-vars=CLEAN_BUCKET_ROW=cleaned-inspection-data-row-434,TRIGGER_URL=https://trigger-931515156181.us-central1.run.app/clean


deploy-loader-parquet:
	docker build -t hygiene_prediction-loader-parquet ./src/loader-parquet
	docker tag hygiene_prediction-loader-parquet us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-parquet
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-parquet
	gcloud run deploy loader-parquet \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/loader-parquet \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300

deploy-trigger:
	@echo "🚀 Building Docker image with embedded Go build step..."
	docker build --no-cache -t hygiene_prediction-trigger -f ./src/trigger/Dockerfile ./src/trigger

	@echo "🔐 Authenticating with Artifact Registry..."
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev

	@echo "📦 Tagging and pushing image to Artifact Registry..."
	docker tag hygiene_prediction-trigger us-central1-docker.pkg.dev/hygiene-prediction-434/containers/trigger
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/trigger

	@echo "🚀 Deploying to Cloud Run..."
	gcloud run deploy trigger \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/trigger \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300


deploy-pipeline-monitor:
	docker build -t hygiene_prediction-pipeline-monitor ./src/dashboards/pl_monitor_dashboard
	docker tag hygiene_prediction-pipeline-monitor us-central1-docker.pkg.dev/hygiene-prediction-434/containers/pipeline-monitor
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/pipeline-monitor
	gcloud run deploy pipeline-monitor \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/pipeline-monitor \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300

deploy-ml-dashboard:
	@export TAG=ml-dashboard:v$$(date +%Y%m%d%H%M%S) && \
	docker build -t $$TAG ./ml_dashboard && \
	docker tag $$TAG us-central1-docker.pkg.dev/hygiene-prediction-434/ml-dashboard-clean/$$TAG && \
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev && \
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/ml-dashboard-clean/$$TAG && \
	gcloud run deploy ml-dashboard \
	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/ml-dashboard-clean/$$TAG \
	  --platform=managed \
	  --region=us-central1 \
	  --allow-unauthenticated \
	  --memory=1Gi \
	  --timeout=300 \
	  --port=8501






# === BUILD ALL: clean everything + rebuild images + start containers ===
build: clean
	@echo "🚀 Building and starting containers..."
	docker-compose up --build -d

# === CLEAN EVERYTHING: remove containers, images, volumes, and cache ===
clean:
	@echo "🧹 Stopping known containers if running..."
	-docker rm -f cleaner trigger extractor loader-json loader-parquet || true
	@echo "🧹 Running docker-compose down..."
	docker-compose down -v --remove-orphans
	@echo "🧼 Pruning Docker images, volumes, and cache..."
	docker system prune -af --volumes

# === STOP containers (optionally one) ===
stop:
	@SERVICE=$(word 2, $(MAKECMDGOALS)); \
	if [ -z "$$SERVICE" ]; then \
		echo "🛑 Stopping all containers..."; \
		docker-compose stop; \
	else \
		echo "🛑 Stopping container: $$SERVICE"; \
		docker-compose stop $$SERVICE; \
	fi

# === START containers (optionally one) ===
start:
	@SERVICE=$(word 2, $(MAKECMDGOALS)); \
	if [ -z "$$SERVICE" ]; then \
		echo "▶️  Starting all containers..."; \
		docker-compose start; \
	else \
		echo "▶️  Starting container: $$SERVICE"; \
		docker-compose start $$SERVICE; \
	fi

# === RESTART all containers ===
restart:
	docker-compose restart

# === SHOW container statuses ===
ps:
	docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# === FULL SYSTEM LOGS ===
logs:
	docker-compose logs -f

# === TAIL logs from a specific service (default: trigger) ===
tail:
	@SERVICE=$(word 2, $(MAKECMDGOALS)); \
	if [ -z "$$SERVICE" ]; then SERVICE=trigger; fi; \
	echo "🔍 Tailing logs from: $$SERVICE"; \
	docker-compose logs -f $$SERVICE

# === EXTRACT via TRIGGER (/run): make extract [rows] [date] ===
extract:
	@MAX=$(or $(word 2, $(MAKECMDGOALS)),$(MAX)); \
	 DATE=$(or $(word 3, $(MAKECMDGOALS)),$(DATE)); \
	 echo "📤 Triggering extract for $$DATE with $$MAX rows..."; \
	 curl -s -X POST http://localhost:8082/run \
	   -H "Content-Type: application/json" \
	   -d "{\"date\": \"$$DATE\", \"max_offset\": $$MAX}"


# === HEALTH: check all ports ===
health:
	@for port in 8081 8082 8083 8084 8085; do \
	  echo "🔎 Checking localhost:$$port..."; \
	  curl -s --max-time 2 http://localhost:$$port || echo "❌ No response on $$port"; \
	  echo ""; \
	done

# === CLEAR GCS BUCKETS (requires gsutil) ===
gcs-clear:
	@echo "🗑 Clearing GCS buckets..."
	@gsutil -m rm -r gs://raw-inspection-data/raw-data/* || true
	@gsutil -m rm -r gs://cleaned-inspection-data-row/clean-data/* || true
	@gsutil -m rm -r gs://cleaned-inspection-data-column/clean-data/* || true
	@echo "✅ GCS buckets cleared."

# === CLEAR BIGQUERY TABLES (preserve schema) ===
bq-clear:
	@echo "🧽 Truncating BigQuery tables..."
	bq query --use_legacy_sql=false \
	  'TRUNCATE TABLE `hygiene-prediction-434.HygienePredictionRow.CleanedInspectionRow`'
	bq query --use_legacy_sql=false \
	  'TRUNCATE TABLE `hygiene-prediction-434.HygienePredictionColumn.CleanedInspectionColumn`'
	@echo "✅ BigQuery tables cleared."

# === TAG & PUSH CONTAINER TO ARTIFACT REGISTRY ===
# 
push:
	@name=$(word 2, $(MAKECMDGOALS)); \
	if [ -z "$$name" ]; then \
		echo "❌ Please provide a service name. Usage: make push trigger"; \
		exit 1; \
	fi; \
	echo "📦 Tagging and pushing image: $$name"; \
	gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin https://us-central1-docker.pkg.dev; \
	docker tag hygiene_prediction-$$name us-central1-docker.pkg.dev/hygiene-prediction-434/containers/$$name; \
	docker push us-central1-docker.pkg.dev/hygiene-prediction-434/containers/$$name


# === DEPLOY TO CLOUD RUN WITH OPTIONAL TRIGGER_URL ===
# === DEPLOY ANY SERVICE TO CLOUD RUN (OPTIONALLY SET TRIGGER_URL) ===
# === DEPLOY EACH SERVICE TO CLOUD RUN (STEP 1) ===
# Note that the python program, deploy/deploy_images.py, in the root directory will perform this 
# automatically for each of the services (it is executable, 
# run ./deploy_images)
#--set-env-vars=$$ENV_VARS

# deploy-cloud-run-%: deploy-cloud-run
# 	@true




# === DEPLOY TRIGGER WITH FULL SERVICE URL CONFIG ===
# === REDEPLOY ALL MICROSERVICES WITH FULL SERVICE CONFIG ===
# deploy-cloud-urls:
# 	@echo "🔍 Fetching Cloud Run service URLs..."
# 	@EXTRACTOR_URL=$$(gcloud run services describe extractor --platform=managed --region=us-central1 --format='value(status.url)') && \
# 	CLEANER_URL=$$(gcloud run services describe cleaner --platform=managed --region=us-central1 --format='value(status.url)') && \
# 	LOADER_JSON_URL=$$(gcloud run services describe loader-json --platform=managed --region=us-central1 --format='value(status.url)') && \
# 	LOADER_PARQUET_URL=$$(gcloud run services describe loader-parquet --platform=managed --region=us-central1 --format='value(status.url)') && \
# 	TRIGGER_URL=$$(gcloud run services describe trigger --platform=managed --region=us-central1 --format='value(status.url)') && \
# 	CONFIG=$$(jq -n --arg ex $$EXTRACTOR_URL \
# 	               --arg cl $$CLEANER_URL \
# 	               --arg lj $$LOADER_JSON_URL \
# 	               --arg lp $$LOADER_PARQUET_URL \
# 	               --arg tr $$TRIGGER_URL \
# 	  '{extractor: {url: $$ex + "/extract"}, \
# 	    cleaner: {url: $$cl + "/clean"}, \
# 	    loader: {url: $$lj + "/load"}, \
# 	    loader_parquet: {url: $$lp + "/load"}, \
# 	    trigger: {url: $$tr + "/clean"}}') && \
# 	CONFIG_B64=$$(echo "$$CONFIG" | base64 -w 0) && \
# 	echo "🚀 Redeploying trigger with full service URLs..." && \
# 	gcloud run deploy trigger \
# 	  --image=us-central1-docker.pkg.dev/hygiene-prediction-434/containers/trigger \
# 	  --platform=managed \
# 	  --region=us-central1 \
# 	  --allow-unauthenticated \
# 	  --memory=1Gi \
# 	  --timeout=300 \
# 	  --set-env-vars=SERVICE_CONFIG_B64=$$CONFIG_B64 && \
# 	echo "✅ Trigger redeployed with full service config."


cloud_deploy:
	@SERVICE=$(word 2, $(MAKECMDGOALS)); \
	if [ -n "$$SERVICE" ]; then \
		echo "🚀 Deploying only: $$SERVICE"; \
		python3 deploy/cloud_deploy.py --only $$SERVICE; \
	else \
		echo "🚀 Running full pipeline deployment..."; \
		python3 deploy/cloud_deploy.py; \
	fi

cloud_deploy-%: cloud_deploy
	@true



# === DESCRIBE ANY SERVICE ON CLOUD RUN ===
describe-cloud-run:
	@SERVICE=$(word 2, $(MAKECMDGOALS)); \
	if [ -z "$$SERVICE" ]; then \
		echo "❌ Usage: make describe-cloud-run <service-name>"; \
		exit 1; \
	fi; \
	echo "📋 Describing Cloud Run service: $$SERVICE"; \
	gcloud run services describe $$SERVICE \
	  --platform=managed \
	  --region=us-central1 \
	  --format="table[box]( \
	    metadata.name:label=SERVICE, \
	    status.url:label=URL, \
	    spec.template.spec.containers[0].env:label=ENV_VARS, \
	    status.latestReadyRevisionName:label=REVISION, \
	    status.conditions[?(@.type=='Ready')].status:label=READY, \
	    status.conditions[?(@.type=='Ready')].message:label=STATUS_MSG \
	  )"


load:
	@if [ -z "$(word 2,$(MAKECMDGOALS))" ]; then \
	  echo "❌ Usage: make load <max_offset>"; \
	else \
	  curl -X POST https://trigger-931515156181.us-central1.run.app/run \
	    -H "Content-Type: application/json" \
	    -d '{"max_offset": '$(word 2,$(MAKECMDGOALS))'}'; \
	fi

%:
	@:

open-ml-db:
	@echo "Opening Cloud Run service in browser..."
	@start https://hygiene-ml-ui-931515156181.us-central1.run.app


delete-cloud:
	@echo "🔴 Deleting all Cloud Run services in hygiene-prediction-434..."
	gcloud run services delete trigger --quiet --region=us-central1 --project=hygiene-prediction-434
	gcloud run services delete extractor --quiet --region=us-central1 --project=hygiene-prediction-434
	gcloud run services delete cleaner --quiet --region=us-central1 --project=hygiene-prediction-434
	gcloud run services delete loader-json --quiet --region=us-central1 --project=hygiene-prediction-434
	gcloud run services delete loader-parquet --quiet --region=us-central1 --project=hygiene-prediction-434
	@echo "✅ Cloud Run services deleted."


deploy-all:
	@echo "🚀 Running full pipeline deployment..."
	python3 deploy/cloud_deploy.py 



trigger_purge:
	@echo "🧹 Purging trigger cache at https://trigger-931515156181.us-central1.run.app/purge..."
	@curl -s -X POST https://trigger-931515156181.us-central1.run.app/purge && echo "✅ Trigger cache cleared."

%:
	@:



# Allow make describe-cloud-run trigger
describe-cloud-run-%: describe-cloud-run
	@true





# === FALLBACK (ignore unknown args like make extract 2000) ===
%:
	@true



# =====================================
# Switch to correct GCP account and project
# =====================================

switch-account:
	@echo "🔄 Switching to account malawley434@gmail.com and project hygiene-prediction-434..."
	gcloud auth login
	gcloud config set account malawley434@gmail.com
	gcloud config set project hygiene-prediction-434
	@echo "✅ Now using account malawley434@gmail.com on project hygiene-prediction-434."

# === ML Dashboard (ml-db) Commands ===

# Hardcoded absolute paths (Windows style)
ML_DB_APP=C:/Users/malaw/OneDrive/Documents/MSDS/MSDS434/hygiene_prediction/src/dashboards/ml_dashboard/app.py
ML_DB_LOG=C:/Users/malaw/OneDrive/Documents/MSDS/MSDS434/hygiene_prediction/src/dashboards/ml_dashboard/ml-db.log

# === ML Dashboard (ml-db) Commands for Windows CMD ===

# Run the ML dashboard in the background (non-blocking)
ml-db:
	@echo Launching ML Dashboard (ml-db) in background...
	start /B streamlit run $(ML_DB_APP) > $(ML_DB_LOG) 2>&1

# Stop the ML dashboard process (Windows version)
ml-db-stop:
	@echo Stopping ML Dashboard (ml-db)...
	@taskkill /F /IM streamlit.exe > NUL 2>&1 || echo No Streamlit process found.

# View the dashboard logs
ml-db-logs:
	@echo Viewing ML Dashboard logs...
	@type $(ML_DB_LOG)

# Clean (delete) dashboard logs
ml-db-clean:
	@echo Cleaning ML Dashboard log file...
	@del /Q $(ML_DB_LOG)

# === GCloud Authentication Setup ===

gcloud-login:
	@echo "🚀 Starting gcloud login (manual)..."
	gcloud auth login --no-launch-browser

gcloud-set-account:
	@echo "🔧 Setting active account to malawley434@gmail.com..."
	gcloud config set account malawley434@gmail.com

gcloud-set-project:
	@echo "🔧 Setting project to hygiene-prediction-434..."
	gcloud config set project hygiene-prediction-434

gcloud-status:
	@echo "📋 Showing current gcloud account and project..."
	gcloud auth list
	gcloud config list project

# === Start ML API (FastAPI service) ===
ml-api:
	@echo "🚀 Starting ML API on port 8090..."
	uvicorn src.dashboards.ml_dashboard.risk_report_service:app --reload --port 8090

# === Start Streamlit Dashboard ===
ml-ui:
	@echo "🧠 Launching Streamlit UI on port 8501..."
	streamlit run src/dashboards/ml_dashboard/app.py

auth-service-account:
	@echo "🔐 Activating service account..."
	gcloud auth activate-service-account --key-file=hygiene-key.json

# Makefile to prepare and run hygiene test configurations

prepare-test:
	@echo "🛠️  Generating configuration JSON files..."
	python prepare_test_configurations.py

run-test:
	@echo "🚀 Running test configurations..."
	python run_test_configurations.py




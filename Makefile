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
	  'TRUNCATE TABLE `hygiene-prediction.HygienePredictionRow.CleanedInspectionRow`'
	bq query --use_legacy_sql=false \
	  'TRUNCATE TABLE `hygiene-prediction.HygienePredictionColumn.CleanedInspectionColumn`'
	@echo "✅ BigQuery tables cleared."

# === FALLBACK (ignore unknown args like make extract 2000) ===
%:
	@true

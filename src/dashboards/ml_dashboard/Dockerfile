# Use a slim Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# === Install shell/debug utilities ===
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    vim \
    less \
    iputils-ping \
    net-tools \
    procps \
 && rm -rf /var/lib/apt/lists/*

# === Copy Python dependencies and install them ===
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# === Copy application code ===
COPY app.py .
COPY risk_report_service.py .
COPY risk_report_generator.py .
COPY hygiene-key.json .
COPY images/ images/
COPY env.local .env


# === Expose ports ===
EXPOSE 8501 8090

# === Default command ===
CMD ["bash", "-c", "uvicorn risk_report_service:app --host 0.0.0.0 --port 8090 & streamlit run app.py --server.port=8501 --server.enableCORS=false"]

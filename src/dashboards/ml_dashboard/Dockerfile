# Use a slim Python base image
FROM python:3.10-slim

# Set working directory inside the container
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

# === Copy requirements and install Python dependencies ===
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt


# === Copy application code ===
COPY app.py .
COPY risk_report_service.py .
COPY risk_report_generator.py .
COPY hygiene-key.json .

# Copy the images needed by the UI
COPY images/ images/

# === Expose ports ===
# Streamlit
EXPOSE 8501   

# FastAPI
EXPOSE 8090   

# === Default command: run both FastAPI and Streamlit ===
CMD ["bash", "-c", "uvicorn risk_report_service:app --host 0.0.0.0 --port 8090 & streamlit run app.py --server.port=8501"]

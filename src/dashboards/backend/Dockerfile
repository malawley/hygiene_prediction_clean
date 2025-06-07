# Use a slim Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install basic utilities
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

# Copy FastAPI app files
COPY risk_report_service.py .
COPY risk_report_generator.py .
COPY requirements.txt .
COPY hygiene-key.json .

# Set environment variable for GCP auth
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/hygiene-key.json"

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# Expose FastAPI port
EXPOSE 8090

# Run FastAPI
CMD ["uvicorn", "risk_report_service:app", "--host", "0.0.0.0", "--port", "8090"]

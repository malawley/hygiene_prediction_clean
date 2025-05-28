# Use a slim official Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc

# Copy code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install streamlit google-cloud-storage google-cloud-bigquery requests

# Expose Cloud Run port
EXPOSE 8080

# Start Streamlit on port 8080 (required by Cloud Run)
CMD ["streamlit", "run", "pipeline_monitor.py", "--server.port=8080", "--server.enableCORS=false"]

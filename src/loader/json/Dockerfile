FROM python:3.11-slim

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p logs


# Copy the loader script
COPY bq_jsonl_loader.py ./bq_jsonl_loader.py

# Create logs directory
RUN mkdir -p logs

# Expose Cloud Run-compatible port
EXPOSE 8080

# HTTP entrypoint for Gunicorn
CMD ["gunicorn", "--timeout", "180", "--bind", "0.0.0.0:8080", "bq_jsonl_loader:wsgi_app"]


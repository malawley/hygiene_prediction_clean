FROM python:3.11-slim

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bq_parquet_loader.py .

# Cloud Run handles logs via stdout/stderr — no log directory needed

EXPOSE 8080

CMD ["gunicorn", "--timeout", "180", "--bind", "0.0.0.0:8080", "bq_parquet_loader:wsgi_app"]



FROM python:3.11-slim

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY run_cleaner.py .
COPY app/ ./app

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run_cleaner:wsgi_app", "--timeout", "180"]





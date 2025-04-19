FROM python:3.11-slim

ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run_cleaner.py .
COPY app/ ./app
COPY services.json /app/services.json

RUN mkdir -p src/logs

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "run_cleaner:wsgi_app", "--timeout", "180"]




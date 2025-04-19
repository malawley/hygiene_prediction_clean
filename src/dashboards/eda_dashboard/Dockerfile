FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY data /app/data


EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.enableCORS=false"]

# Use a slim Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# === Install dependencies ===
RUN apt-get update && apt-get install -y \
    bash \
    curl \
    vim \
    less \
    && rm -rf /var/lib/apt/lists/*

# === Copy requirements and install ===
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# === Copy Streamlit app code ===
COPY app.py .
COPY env.local .env
COPY images/ images/

# === Expose Streamlit port ===
EXPOSE 8501

# === Launch Streamlit ===
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.enableCORS=false"]

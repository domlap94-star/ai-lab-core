# Match the Python patch release in the current known-good backend image.
FROM python:3.12.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y \
        --no-install-recommends \
        antiword \
        libreoffice-writer \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

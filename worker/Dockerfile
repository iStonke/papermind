FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ocrmypdf \
        tesseract-ocr \
        tesseract-ocr-deu \
        tesseract-ocr-eng \
        unpaper \
        ghostscript \
        qpdf \
        libgl1 \
        libglib2.0-0 \
        libheif1 \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/app /app/app

CMD ["python", "-m", "app.worker.main"]

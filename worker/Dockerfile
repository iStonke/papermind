FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update -o Acquire::Retries=5 \
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
        curl \
        ca-certificates \
        gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && (curl -fsSL --connect-timeout 15 --retry 5 --retry-delay 2 --retry-connrefused --retry-all-errors \
        https://apt.postgresql.org/pub/repos/apt/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        || curl -fsSL --connect-timeout 15 --retry 5 --retry-delay 2 --retry-connrefused --retry-all-errors \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc) \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update -o Acquire::Retries=5 \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/*

COPY worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Dieselben lokalen Piper-Stimmen wie im Backend. Der Worker rendert lange
# Notizexporte unabhängig vom Browser und benötigt deshalb Modelle + Runtime.
ARG PIPER_VOICE=de_DE-thorsten-high
ARG PIPER_VOICE_SHA256=9df1c43c61149ef9b39e618e2b861fbe41e1fcea9390b2dac62e8761573ea4f1
ARG PIPER_CONFIG_SHA256=6de734444e4c3f9e33b7ebe2746dbc19b71e85f613e79c65acf623200b99a76a
ARG PIPER_EMOTIONAL_VOICE=de_DE-thorsten_emotional-medium
ARG PIPER_EMOTIONAL_VOICE_SHA256=c1764e652266cd6dcebf1b95c61973df5970a5f5272e94b655ff1ddf9a99d1ff
ARG PIPER_EMOTIONAL_CONFIG_SHA256=92895b9e99f7cfc13f4a9879da615c3d6e0baa4d660e26d7b685abdd27a6d1d3
ARG PIPER_ENGLISH_VOICE=en_US-ryan-high
ARG PIPER_ENGLISH_VOICE_SHA256=b3990d7606e183ec8dbfba70a4607074f162de1a0c412e0180d1ff60bb154eca
ARG PIPER_ENGLISH_CONFIG_SHA256=c6d3b98f08315cb4bebf0d49d50fc4ff491b503c64b940cd3d5ca28543b48011
RUN install -d /opt/piper-voices \
    && python -m piper.download_voices --download-dir /opt/piper-voices \
        "${PIPER_VOICE}" "${PIPER_EMOTIONAL_VOICE}" "${PIPER_ENGLISH_VOICE}" \
    && echo "${PIPER_VOICE_SHA256}  /opt/piper-voices/${PIPER_VOICE}.onnx" | sha256sum -c - \
    && echo "${PIPER_CONFIG_SHA256}  /opt/piper-voices/${PIPER_VOICE}.onnx.json" | sha256sum -c - \
    && echo "${PIPER_EMOTIONAL_VOICE_SHA256}  /opt/piper-voices/${PIPER_EMOTIONAL_VOICE}.onnx" | sha256sum -c - \
    && echo "${PIPER_EMOTIONAL_CONFIG_SHA256}  /opt/piper-voices/${PIPER_EMOTIONAL_VOICE}.onnx.json" | sha256sum -c - \
    && echo "${PIPER_ENGLISH_VOICE_SHA256}  /opt/piper-voices/${PIPER_ENGLISH_VOICE}.onnx" | sha256sum -c - \
    && echo "${PIPER_ENGLISH_CONFIG_SHA256}  /opt/piper-voices/${PIPER_ENGLISH_VOICE}.onnx.json" | sha256sum -c -

ENV TTS_MODEL_PATH=/opt/piper-voices/${PIPER_VOICE}.onnx
ENV TTS_EMOTIONAL_MODEL_PATH=/opt/piper-voices/${PIPER_EMOTIONAL_VOICE}.onnx
ENV TTS_ENGLISH_MODEL_PATH=/opt/piper-voices/${PIPER_ENGLISH_VOICE}.onnx

COPY backend/app /app/app

CMD ["python", "-m", "app.worker.main"]

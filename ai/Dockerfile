FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/papermind XDG_CACHE_HOME=/tmp/papermind-cache
RUN install -d -m 0755 -o 1000 -g 1000 /home/papermind

WORKDIR /app

RUN apt-get update -o Acquire::Retries=5 \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 11434

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "11434", "--reload", "--reload-dir", "/app/app"]

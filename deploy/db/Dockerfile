FROM pgvector/pgvector:0.8.7-pg17-bookworm@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d

# Keep the existing PostgreSQL major and Debian generation for the data volume.
RUN apt-get update -o Acquire::Retries=5 \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

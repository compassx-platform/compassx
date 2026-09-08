ARG REGISTRY_PREFIX
FROM python:3.11-slim
ARG PIP_INDEX_URL
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /ms-home
COPY requirements.txt .
# Install CPU-only PyTorch first to prevent downloading ~2GB CUDA binaries
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["/bin/sh", "-c", "\
  set -euo pipefail; \
  if [ -f /var/secrets/env ]; then \
    set -a; source /var/secrets/env; set +a; \
  fi; \
    exec python app.py \
"]

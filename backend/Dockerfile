ARG REGISTRY_PREFIX
FROM python:3.11-slim
ARG PIP_INDEX_URL
# RUN adduser -D -u 1002 python
WORKDIR /ms-home
COPY requirements.txt .
# Install directly from the configured/default index to avoid SSL failures
# against the separate PyTorch wheel host in restricted corporate networks.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["/bin/sh", "-c", "\
  set -euo pipefail; \
  if [ -f /var/secrets/env ]; then \
    set -a; source /var/secrets/env; set +a; \
  fi; \
    exec python app.py \
"]

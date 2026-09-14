FROM python:3.12-slim-bookworm AS builder
ENV DEBIAN_FRONTEND=noninteractive

# Prepare keyrings and apt sources for Docker CLI and Trivy (no heavy installs here)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release \
    ca-certificates \
    wget \
    apt-transport-https && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    bash -c 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list' && \
    wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg && \
    bash -c 'echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" > /etc/apt/sources.list.d/trivy.list' && \
    rm -rf /var/lib/apt/lists/*

FROM python:3.12-slim-bookworm

ARG TARGETARCH
ARG COSIGN_VERSION=v3.0.2

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBIAN_FRONTEND=noninteractive

COPY --from=builder /etc/apt/keyrings/docker.gpg /etc/apt/keyrings/docker.gpg
COPY --from=builder /etc/apt/sources.list.d/docker.list /etc/apt/sources.list.d/docker.list
COPY --from=builder /usr/share/keyrings/trivy.gpg /usr/share/keyrings/trivy.gpg
COPY --from=builder /etc/apt/sources.list.d/trivy.list /etc/apt/sources.list.d/trivy.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      git \
      ca-certificates \
      docker-ce-cli \
      docker-buildx-plugin \
      trivy \
      clamav \
      clamav-freshclam && \
    rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
      amd64|arm64) cosign_arch="${TARGETARCH}" ;; \
      *) echo "Unsupported architecture for cosign: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-${cosign_arch}" \
      -o /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN freshclam
# App code
COPY main.py .
COPY src/ ./src/

ENTRYPOINT ["python", "main.py"]

FROM python:3.12-slim-bookworm AS builder
ENV DEBIAN_FRONTEND=noninteractive

# Prepare keyrings and apt sources for Docker CLI and Trivy (no heavy installs here)
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
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
ARG OPENGREP_VERSION=v1.30.2

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBIAN_FRONTEND=noninteractive

COPY --from=builder /etc/apt/keyrings/docker.gpg /etc/apt/keyrings/docker.gpg
COPY --from=builder /etc/apt/sources.list.d/docker.list /etc/apt/sources.list.d/docker.list
COPY --from=builder /usr/share/keyrings/trivy.gpg /usr/share/keyrings/trivy.gpg
COPY --from=builder /etc/apt/sources.list.d/trivy.list /etc/apt/sources.list.d/trivy.list

RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
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

# Pin OpenGrep and verify the release asset digest for each supported architecture.
RUN case "${TARGETARCH}" in \
      amd64) opengrep_arch="x86"; opengrep_sha="a66aa3278457f02b287b985a45b6762aebcaba5000f2689245fd1ed86d1456c7" ;; \
      arm64) opengrep_arch="aarch64"; opengrep_sha="90acea5df4b733083f388d4feeb250ca802f671b33d1f222653d1e571dd2b0d8" ;; \
      *) echo "Unsupported architecture for OpenGrep: ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/opengrep/opengrep/releases/download/${OPENGREP_VERSION}/opengrep_manylinux_${opengrep_arch}" \
      -o /usr/local/bin/opengrep && \
    echo "${opengrep_sha}  /usr/local/bin/opengrep" | sha256sum -c - && \
    chmod +x /usr/local/bin/opengrep

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# definitions are baked in, so local builds also scan without internet access
RUN freshclam && trivy image --download-db-only
# App code
COPY main.py .
COPY src/ ./src/
# Smoke-test the bundled rules without fetching registry lints.
RUN opengrep scan --strict --config /app/src/sast/fl-net.yml --disable-version-check \
      --json /app/src/steps/sast.py > /dev/null

ENTRYPOINT ["python", "main.py"]

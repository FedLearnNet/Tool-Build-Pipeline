#!/usr/bin/env bash
# Small helper script to build the pipeline image locally to use in testing.
# orch-api only starts the pipeline image under its ghcr name (any tag), so the local image has to
# carry that name. With a tag that does not exist on ghcr the pull fails and orch-api uses this one.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

TAG=testingtag

docker build -t "ghcr.io/fedlearnnet/tool-build-pipeline/pipeline:$TAG" "$REPO_ROOT"

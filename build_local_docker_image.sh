#!/usr/bin/env bash
# Small helper script to build the pipeline image locally to use in testing.
# orch-api only starts the pipeline image under its ghcr name (any tag), so the local image has to
# carry that name. With a tag that does not exist on ghcr the pull fails and orch-api uses this one.
set -euo pipefail
cd "$(dirname "$0")"

TAG=tmptag

docker build -t "ghcr.io/fedlearnnet/tool-build-pipeline/pipeline:$TAG" .

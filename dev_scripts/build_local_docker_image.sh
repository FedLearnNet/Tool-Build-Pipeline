#!/bin/sh
# Small helper script to build the pipeline image locally to use in the testing bundle.
# orch-api only starts the pipeline image under its ghcr name (any tag), so the local image has to
# carry that name. With a tag that does not exist on ghcr the pull fails and orch-api uses this one.
set -eu
cd "$(dirname "$0")/.."

# The testing bundle always pulls new images on startup but ignores this tag, 
# so keep the tag if you wanna use it in the testing bundle
TAG="${1:-testingtag}"


docker build -t "ghcr.io/fedlearnnet/tool-build-pipeline/pipeline:$TAG" .


# Docker Build & Push Pipeline Client

This project is a containerized pipeline client that runs inside a Docker container and executes a predefined build pipeline.
The pipeline fetches its configuration from a remote server, builds and scans a Docker image, and reports the result of each step back to the server.

The client is designed to be stateless, repeatable, and fully driven by environment variables.


## Overview

At runtime the pipeline:
	1.	Loads configuration from environment variables
	2.	Connects to a backend API
	3.	Executes a fixed sequence of pipeline steps
	4.	Reports logs, progress, and success/failure for each step back to the server

If a mandatory step fails, the pipeline stops immediately.
Optional steps (e.g. security scanning) may fail without aborting the pipeline.


## Pipeline Steps

The pipeline runs the following steps in order:

### FetchConfigStep (FETCH_CONFIG)

Fetches the pipeline run configuration from the server via the API.
This includes repository URL, image name, image tag, and other runtime metadata.
The result is stored in AppConfig.remote_info and used by all subsequent steps.

### CloneRepoStep (CLONE_REPO)

Clones the target Git repository into a clean local workspace.
If the repository is hosted on GitLab, an access token is injected automatically.
Any existing workspace directory is removed before cloning.

### FetchFilesStep (FETCH_FILES)

Fetches additional files from the server (e.g. injected configs, secrets, or templates).
Files are transferred as base64 payloads and written into the local workspace.
Progress updates are streamed back to the server during this step.

### BuildImageStep (BUILD_IMAGE)

Builds the Docker image from the cloned repository.
- Optional Docker registry login
- Supports standard docker build
- Keeps a local single-platform image available for scan/test steps
- Image name and tag are derived from the remote pipeline configuration

### RunPytestStep (RUN_PYTEST)

Executes pytest against the injected main.py file located in the workspace.
- Runs real pytest execution
- Fails the pipeline if tests fail
- Ensures runtime validation of the application before publishing

### ScanImageStep (SCAN_IMAGE) (Allow to fail)

Scans the built Docker image using Trivy for HIGH and CRITICAL vulnerabilities.
- Produces structured scan output
- Fails the step if vulnerabilities are found
- Does not fail the pipeline (allow_to_fail = true)
- Results are still reported to the server

###  MalwareCheckRepoStep (MALWARE_CHECK_REPO)

Scans the cloned Git repository (including .git directory unless configured otherwise) using ClamAV.
- Detects malicious files in source code
- Fails the pipeline if malware is detected
- Stores a structured malware scan result
- Reports detailed logs back to the server

This ensures repository integrity before building the image.

###  PushImageStep (PUSH_IMAGE)

Pushes the built Docker image to the configured Docker registry.
The image name is fully deterministic and derived from the pipeline run metadata.
- Uses `docker buildx build --push` when `use_buildx=true`
- Publishes SBOM attestations by default via `--sbom=true`
- Publishes provenance attestations by default via `--provenance=mode=max`
- Supports optional Cosign signing after a successful push

### CollectSummaryStep (COLLECT_SUMMARY)

Builds a final publish summary and uploads it to the server.

The summary contains:
- Git commit hash
- Docker image name
- List of file paths (as raw Git file links)
- Vulnerability scan result
- Malware scan result

##  Configuration

Configuration is handled via pydantic-settings and environment variables.

An optional .env file is supported for local development.

Notable container publishing settings:
- `USE_BUILDX=true` enables registry builds through `docker buildx`
- `BUILDX_PLATFORMS` controls the configured multi-arch targets
- `BUILDX_SBOM=true` enables SBOM attestations on the push build
- `BUILDX_PROVENANCE_MODE=max` enables provenance attestations on the push build
- `COSIGN_SIGN=false` optionally signs the pushed image with `cosign sign --yes`

When `COSIGN_SIGN=true`, the pipeline runner image must contain the `cosign` binary. This repository's
`Dockerfile` installs `cosign` for the runner container; it does not need to be added to the application image
that is being built and published.

## Execution Flow

The application entrypoint:
1.	Prints a startup banner
2.	Configures structured logging
3.	Loads configuration 
4. Initializes the API client 
5. Runs the pipeline 
6. Exits with a non-zero code on fatal errors

Each step reports:
- Status (RUNNING, SUCCESS, FAILED)
- Logs
- Progress updates

### Failure Handling
- Mandatory steps: failure aborts the pipeline immediately
- Optional steps: failure is logged and reported, pipeline continues
- All critical errors cause the container to exit with code 1

## Intended Usage

This client is intended to be run:
- As a Docker container
- Triggered by an external orchestrator or CI system
- Fully controlled by environment variables
- Connected to a backend service that tracks pipeline runs

# Testing

The project includes both:

## Unit tests (pytest-based)
- Tests for pipeline flow
- Validation of Pydantic models
- Mocked backend responses

Run:
```bash
pytest -q
```
## Pipeline test for dev. (test.py)
- Tests for pipeline flow
- Validation of Pydantic models
- Mocked backend responses

Run:
```bash
python test.py
```
# Summary

This pipeline client provides a clean, deterministic, and extensible way to:
- Build Docker images remotely
- Inject server-side configuration and files
- Perform security scans
- Push images to a registry
- Report step-by-step results back to a central server

It is optimized for automated, reproducible, and auditable build pipelines.

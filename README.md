# FL-Net Tool Build Pipeline

A containerized, stateless pipeline client that builds, tests, scans and publishes Docker images of FL-Net
tools. It fetches its run configuration from the platform, executes a fixed sequence of steps and reports
status, logs and progress of every step back to the server. It is normally started by
[orch-api](https://github.com/FedLearnNet/Orchestration-API) when a tool is published.

Part of FL-Net, the federated learning platform also behind PosyMed.

## Documentation

- [FL-Net documentation](https://federated-learning.net/documentation/)


## Running

The container needs access to the Docker socket. For a local run, copy `.env.example` to `.env`, fill in the
values and start it:

```bash
docker compose up --build
```

## Configuration

All settings come from environment variables (or a `.env` file), loaded in [`src/config.py`](src/config.py).

Select a mode with `RUN_MODE`:

| Mode | Steps after fetching configuration |
| --- | --- |
| `ALL` (default) | Clone `main`, inject files, SAST, build, Trivy, ClamAV, tests, push, summary |
| `LOCAL_BUILD` | Fetch ZIP as the build context, SAST, build, offline Trivy, ClamAV, tests without network, summary |
| `SCAN_ONLY` | Pull the existing image, Trivy vulnerability rescan, summary |

`ALL` tags the image with the cloned commit hash and includes that hash in the build summary.
`LOCAL_BUILD` builds an image that stays on the Docker host, as the local learning API does for custom
transformers. It uses the API's `imageName:dockerTag` without a registry prefix. SAST rules and Trivy/ClamAV
databases are baked into the pipeline image. It skips clone and push, and the test container runs with
`--network none`.

The orchestrator supplies `RUN_MODE` as `ALL`, `LOCAL_BUILD`, or `SCAN_ONLY`.

Local builds use the pipeline image as `fl-net/tool-build-pipeline:dev`:

```bash
docker build -t fl-net/tool-build-pipeline:dev .
```

### Rescanning a published image

```bash
RUN_MODE=SCAN_ONLY DOCKER_TAG=your-existing-tag docker compose up --build
```

Here `--build` builds the pipeline client container. The tool image is **never rebuilt or republished**.
The target is `<DOCKER_REGISTRY>/<DOCKER_GROUP>/<imageName>:<tag>`, using the API's `dockerTag`, or an
explicit `DOCKER_TAG` when the API does not provide one. A missing tag fails the run; it does not silently
scan `latest` or clone the current source. Explicitly selecting `latest` is supported.

The pipeline always pulls the target so a stale local tag cannot be reused. Private registries use
`DOCKER_LOGIN=true` and `DOCKER_USERNAME`/`DOCKER_PASSWORD`, or existing Docker credentials. A failed pull
stops the run. Trivy reads the pulled Docker image for the host platform and refreshes its vulnerability
database. The rescan skips source fetching, SAST, malware scanning, container execution, and publishing.
The summary contains `imageName` and `vulnerabilityScanResult`; source and other scan fields are omitted.

### SAST policy

The `SAST` step runs [OpenGrep](https://github.com/opengrep/opengrep) before image building, after files
have been injected. The pipeline image pins version `1.30.2` and verifies release checksums on amd64
and arm64. Update the version and matching checksums together in `Dockerfile`.

[`src/sast/fl-net.yml`](src/sast/fl-net.yml) contains 12 platform-owned rules focused on Python FL-Net
tools: dynamic code/shell execution, unsafe YAML, pickle/dill/joblib and PyTorch model loading, disabled
TLS verification, temporary files, archive extraction, debug servers, hardcoded credentials, remote
Docker `ADD`, and Python object tags in YAML. These are targeted checks, not complete language coverage.
Model deserialization is advisory because trusted ML artifacts commonly use these formats.

The scan uses bundled rules without runtime registry downloads. Repository ignore files and `nosem`
comments cannot suppress the platform policy. Virtual environments, dependency/cache directories,
notebooks, and binary data/model artifacts are excluded; Python code in `models/` and tests is scanned.
`SAST_TIMEOUT` (default 30 seconds per rule/file) and `SAST_MAX_TARGET_BYTES` (default 1 MB per file)
bound the work. Parse errors, timeouts, and scans with no source files produce warnings instead of a
clean result.

Findings appear in step logs with file, line, rule, and remediation text. The summary's
`sastScanResult` uses its own DTO with typed findings (rule ID, native `ERROR`/`WARNING`/`INFO` severity,
message, relative file path, line/column range, and rule metadata), native severity counts, scanner
version, scanned file count, scan errors, and the raw report. `complete` distinguishes a finished scan
with findings from a partial or failed scan; `success` also requires no findings. SAST and Trivy
findings are warnings and do not prevent subsequent steps,
matching the existing vulnerability scan policy. Malware findings still stop builds.

This change is confined to Tool-Build-Pipeline. Backend storage/UI support for `sastScanResult` and
scheduling `SCAN_ONLY` runs must be provided by the calling platform; the current backend DTO does not
yet persist the new SAST field.

## Testing

```bash
pip install -r requirements.test.txt
pytest -q          # unit and pipeline integration tests with mocked commands/API
python test.py     # local pipeline run for development
```

Tests mock OpenGrep and Trivy execution and check command construction, report parsing, status
callbacks, summaries, scanner failures, and all run modes. They require no
scanner installation, Docker, or network access. OpenGrep is installed in the pipeline's Docker image.
`python test.py` is a development harness that still clones/builds/runs a real tool.


## License

[Apache License 2.0](LICENSE) © Institute for Computational Systems Biomedicine and contributors.

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


## Testing

```bash
pip install -r requirements.test.txt
pytest -q          # unit tests with mocked backend responses
python test.py     # local pipeline run for development
```



## License

[Apache License 2.0](LICENSE) © Institute for Computational Systems Biomedicine and contributors.

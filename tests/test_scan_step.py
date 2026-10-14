import json
import os

import pytest

from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.client.dto import PipelineRunInfoDTO
from src.steps.scan import ScanImageStep


class DummyApiClient:
    def send_status_update(self, update_dto):
        return None


class RecordingScanImageStep(ScanImageStep):
    def __init__(self, config, api_client, result, return_code, report):
        super().__init__(config, api_client, result)
        self.return_code = return_code
        self.report = report
        self.report_path = None
        self.command = None

    def _run_command(self, command, cwd=".", env=None):
        self.command = command
        self.report_path = command[command.index("--output") + 1]
        if self.report is None:
            os.remove(self.report_path)
        else:
            with open(self.report_path, "w", encoding="utf-8") as report_file:
                report_file.write(self.report)
        return self.return_code, "", "trivy stderr"


def make_step(return_code, report, local_only=False) -> RecordingScanImageStep:
    config = AppConfig(
        local_only=local_only,
        docker_registry="registry.example.com",
        docker_group="/team/apps",
        remote_info=PipelineRunInfoDTO(
            gitRepoUrl="https://example.com/demo.git",
            imageName="demo-app",
        ),
    )
    config.set_docker_tag("a" * 40)
    return RecordingScanImageStep(config, DummyApiClient(), AppPublishInfoDTO(commitHash="a" * 40), return_code, report)


def report_with_high_findings(count: int) -> str:
    return json.dumps({
        "Results": [{
            "Class": "lang-pkgs",
            "Type": "python-pkg",
            "Vulnerabilities": [{"VulnerabilityID": f"CVE-{i}", "Severity": "HIGH"} for i in range(count)],
        }]
    })


@pytest.mark.parametrize("local_only", [False, True])
def test_clean_scan_still_sets_the_result(local_only):
    step = make_step(0, json.dumps({"Results": []}), local_only)

    step.execute()

    scan_result = step.result.vulnerability_scan_result
    assert scan_result is not None
    assert scan_result.success is True
    assert scan_result.summary.get_num() == 0
    assert scan_result.target == step.config.get_docker_name()
    assert ("--skip-db-update" in step.command) == local_only
    assert ("--offline-scan" in step.command) == local_only
    assert not os.path.exists(step.report_path)


@pytest.mark.parametrize("local_only", [False, True])
def test_findings_set_the_result_and_fail_the_step(local_only):
    step = make_step(1, report_with_high_findings(2), local_only)

    with pytest.raises(Exception, match="Trivy found 2 HIGH/CRITICAL vulnerabilities"):
        step.execute()

    scan_result = step.result.vulnerability_scan_result
    assert scan_result.success is False
    assert scan_result.summary.high == 2
    assert len(scan_result.raw_report["lang-pkgs-python-pkg"]) == 2
    assert not os.path.exists(step.report_path)


@pytest.mark.parametrize("local_only", [False, True])
def test_missing_report_fails_with_the_trivy_error(local_only):
    step = make_step(2, None, local_only)

    with pytest.raises(Exception, match="Trivy scan failed. Error: trivy stderr"):
        step.execute()

    assert step.result.vulnerability_scan_result is None

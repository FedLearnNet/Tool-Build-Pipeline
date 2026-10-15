import io
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.client.dto import PipelineRunInfoDTO
from src.config import AppConfig, RunMode
from src.pipeline import Pipeline
from src.steps.base import BaseStep


@pytest.mark.parametrize("mode", list(RunMode))
@pytest.mark.parametrize("findings", [False, True])
def test_pipeline_runs_production_steps_with_mocked_commands(tmp_path, monkeypatch, mode, findings):
    repo = tmp_path / "repo"
    config = AppConfig(_env_file=None, run_mode=mode, repo_path=str(repo), use_buildx=False)
    info = PipelineRunInfoDTO(
        gitRepoUrl="https://example.com/tool.git", imageName="demo", dockerTag="published-commit",
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("main.py", "print('tool')\n")
    client = MagicMock()
    client.get_pipeline_info.return_value = info
    client.get_zip_for_pipeline.return_value = buffer.getvalue()
    commands = []

    def run_command(step, command, cwd=".", env=None):
        commands.append(command)
        if command[:2] == ["git", "clone"]:
            repo.mkdir()
            return 0, "", ""
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return 0, "a" * 40, ""
        if command[:2] == ["opengrep", "scan"]:
            report = {"results": [{
                "check_id": "flnet.python.dynamic-code-execution", "path": str(repo / "main.py"),
                "start": {"line": 1, "col": 1}, "end": {"line": 1, "col": 10},
                "extra": {"severity": "ERROR", "message": "Avoid eval on tool inputs."},
            }] if findings else [], "errors": []}
            Path(command[command.index("--output") + 1]).write_text(json.dumps(report))
            return int(findings), "", ""
        if command[:2] == ["trivy", "image"]:
            report = {"Results": [{"Class": "os-pkgs", "Type": "debian", "Vulnerabilities": [
                {"VulnerabilityID": "CVE-test", "Severity": "HIGH"},
            ]}] if findings else []}
            Path(command[command.index("--output") + 1]).write_text(json.dumps(report))
            return int(findings), "", ""
        if command[0] == "clamscan" or command[:2] in [
            ["docker", "build"], ["docker", "run"], ["docker", "push"], ["docker", "pull"],
        ]:
            return 0, "", ""
        if command[:3] == ["docker", "buildx", "version"]:
            return 0, "", ""
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(BaseStep, "_run_command", run_command)
    pipeline = Pipeline(config, client)

    pipeline.run()

    client.upload_summary.assert_called_once_with(pipeline.result)
    assert pipeline.result.vulnerability_scan_result.success == (not findings)
    statuses = [call.args[0].status for call in client.send_status_update.call_args_list]
    assert "FAILED" not in statuses
    assert ("WARNING" in statuses) == findings
    assert statuses[-1] == "SUCCESS"
    if mode == RunMode.SCAN_ONLY:
        assert [command[0] for command in commands] == ["docker", "trivy"]
        assert pipeline.result.image_name.endswith(":published-commit")
        assert not repo.exists()
        assert pipeline.result.commit_hash is None
        assert pipeline.result.file_paths is None
        assert pipeline.result.sast_scan_result is None
        client.get_zip_for_pipeline.assert_not_called()
    else:
        assert pipeline.result.sast_scan_result.success == (not findings)
        assert (any(cmd[:2] == ["docker", "push"] for cmd in commands)) == (mode == RunMode.ALL)


def test_failed_pull_stops_rescan_before_scanning(tmp_path, monkeypatch):
    config = AppConfig(_env_file=None, run_mode=RunMode.SCAN_ONLY, repo_path=str(tmp_path / "missing"))
    client = MagicMock()
    client.get_pipeline_info.return_value = PipelineRunInfoDTO(imageName="demo", dockerTag="existing")
    command = MagicMock(return_value=(1, "", "manifest unknown"))
    monkeypatch.setattr(BaseStep, "_run_command", command)
    with pytest.raises(Exception, match="Docker pull failed"):
        Pipeline(config, client).run()
    assert command.call_count == 1
    client.upload_summary.assert_not_called()

import json
import os
from unittest.mock import MagicMock

import pytest

from src.client.result_dto import AppPublishInfoDTO, SastFindingDTO, SastScanErrorDTO, SastScanResultDTO
from src.config import AppConfig, RunMode
from src.steps.sast import RULES_PATH, SastStep


def make_step(tmp_path, report, return_code=0):
    config = AppConfig(_env_file=None, repo_path=str(tmp_path), run_mode=RunMode.LOCAL_BUILD)
    step = SastStep(config, MagicMock(), AppPublishInfoDTO())

    def command(command, cwd=".", env=None):
        step.command = command
        step.report_path = command[command.index("--output") + 1]
        with open(step.report_path, "w") as output:
            output.write(report if isinstance(report, str) else json.dumps(report))
        return return_code, "", "opengrep stderr"

    step._run_command = command
    return step


def test_clean_sast_reports_success_with_bundled_rules_and_no_suppressions(tmp_path):
    step = make_step(tmp_path, {"version": "1.30.2", "results": [], "errors": [],
                                "paths": {"scanned": ["main.py"]}})
    step.execute()
    result = step.result.sast_scan_result
    assert result.success
    assert isinstance(result, SastScanResultDTO)
    assert result.complete
    assert result.scanned_files == 1
    assert result.version == "1.30.2"
    assert result.findings == []
    assert result.errors == []
    assert result.tool == "opengrep"
    assert result.summary.get_num() == 0
    assert step.command[step.command.index("--config") + 1] == str(RULES_PATH)
    assert "--disable-nosem" in step.command
    assert "--x-ignore-semgrepignore-files" in step.command
    assert "--no-git-ignore" in step.command
    assert not os.path.exists(step.report_path)
    assert "sastScanResult" in step.result.model_dump(by_alias=True, exclude_none=True)


def test_findings_are_counted_and_recorded_as_advisory_warning(tmp_path):
    report = {"results": [{
        "check_id": f"flnet.rule-{i}", "path": str(tmp_path / "main.py"),
        "start": {"line": i + 1, "col": 3}, "end": {"line": i + 1, "col": 20},
        "extra": {"severity": s, "message": "Use the safe alternative.",
                  "metadata": {"cwe": ["CWE-95"]}},
    } for i, s in enumerate(["ERROR", "WARNING", "INFO", "other"])], "errors": []}
    step = make_step(tmp_path, report, return_code=1)
    with pytest.raises(RuntimeError, match="OpenGrep found 4 SAST findings"):
        step.run()
    result = step.result.sast_scan_result
    assert not result.success
    assert result.complete
    assert (result.summary.error, result.summary.warning, result.summary.info, result.summary.unknown) == (1, 1, 1, 1)
    assert all(isinstance(finding, SastFindingDTO) for finding in result.findings)
    finding = result.findings[0]
    assert finding.rule_id == "flnet.rule-0"
    assert finding.file_path == "main.py"
    assert (finding.start_line, finding.end_line, finding.start_column, finding.end_column) == (1, 1, 3, 20)
    assert finding.message == "Use the safe alternative."
    assert finding.metadata == {"cwe": ["CWE-95"]}
    assert result.findings[-1].severity == "UNKNOWN"
    assert result.raw_report == report
    assert step.api_client.send_status_update.call_args.args[0].status == "WARNING"
    assert not os.path.exists(step.report_path)
    payload = step.result.model_dump(by_alias=True, exclude_none=True)
    assert payload["sastScanResult"]["summary"] == {"error": 1, "warning": 1, "info": 1, "unknown": 1}
    assert payload["sastScanResult"]["findings"][0] == {
        "ruleId": "flnet.rule-0", "severity": "ERROR", "message": "Use the safe alternative.",
        "filePath": "main.py", "startLine": 1, "endLine": 1, "startColumn": 3, "endColumn": 20,
        "metadata": {"cwe": ["CWE-95"]},
    }
    assert AppPublishInfoDTO.model_validate(payload).sast_scan_result == result


@pytest.mark.parametrize("report", ["bad json", {}, []])
def test_invalid_report_is_not_reported_as_clean(tmp_path, report):
    step = make_step(tmp_path, report, return_code=2)
    with pytest.raises(RuntimeError, match="OpenGrep scan failed"):
        step.execute()
    assert step.result.sast_scan_result is None
    assert not os.path.exists(step.report_path)


def test_parse_errors_are_incomplete_even_with_no_findings(tmp_path):
    step = make_step(tmp_path, {"results": [], "errors": [{
        "type": "ParseError", "message": "Invalid syntax", "code": 3,
        "level": "warn", "path": str(tmp_path / "main.py"),
    }]})
    with pytest.raises(RuntimeError, match="OpenGrep scan incomplete"):
        step.execute()
    assert not step.result.sast_scan_result.success
    assert not step.result.sast_scan_result.complete
    error = step.result.sast_scan_result.errors[0]
    assert isinstance(error, SastScanErrorDTO)
    assert error.error_type == "ParseError"
    assert error.message == "Invalid syntax"
    assert error.file_path == "main.py"
    assert error.model_dump(by_alias=True) == {
        "type": "ParseError", "message": "Invalid syntax", "level": "warn", "code": 3,
        "filePath": "main.py",
    }


def test_empty_scan_is_not_reported_as_clean(tmp_path):
    step = make_step(tmp_path, {"results": [], "errors": [], "paths": {"scanned": []}})
    with pytest.raises(RuntimeError, match="OpenGrep scanned no source files"):
        step.execute()
    assert not step.result.sast_scan_result.success
    assert not step.result.sast_scan_result.complete
    assert step.result.sast_scan_result.scanned_files == 0


@pytest.mark.parametrize("return_code", [1, 2])
def test_scanner_failure_without_findings_is_incomplete(tmp_path, return_code):
    step = make_step(tmp_path, {"results": [], "errors": []}, return_code=return_code)
    with pytest.raises(RuntimeError, match="OpenGrep scan (failed|incomplete)"):
        step.execute()
    assert not step.result.sast_scan_result.success
    assert not step.result.sast_scan_result.complete


def test_malformed_finding_does_not_produce_a_successful_or_partial_result(tmp_path):
    step = make_step(tmp_path, {"results": [{"extra": {"severity": "ERROR"}}]}, return_code=1)
    with pytest.raises(RuntimeError, match="OpenGrep scan failed"):
        step.execute()
    assert step.result.sast_scan_result is None


def test_command_failure_cleans_up_report(tmp_path):
    step = make_step(tmp_path, {})

    def missing_binary(command, **kwargs):
        step.report_path = command[command.index("--output") + 1]
        raise FileNotFoundError("opengrep")

    step._run_command = missing_binary
    with pytest.raises(FileNotFoundError):
        step.execute()
    assert not os.path.exists(step.report_path)

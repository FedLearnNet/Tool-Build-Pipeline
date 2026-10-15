import json
import logging
import os
import tempfile
from pathlib import Path

from src.client.result_dto import SastFindingDTO, SastScanErrorDTO, SastScanResultDTO, SastSummaryDTO
from src.steps.base import BaseStep

logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).resolve().parents[1] / "sast" / "python.yml"
EXCLUDES = (
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "*.csv", "*.parquet", "*.pkl", "*.pickle", "*.pt", "*.pth", "*.onnx",
)


class SastStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "SAST"

    @property
    def allow_to_fail(self) -> bool:
        return True

    @staticmethod
    def _relative_path(path: str, target: Path) -> str:
        try:
            return str(Path(path).relative_to(target))
        except ValueError:
            return path

    def parse_opengrep_result(self, report: dict, target: Path, exit_code: int) -> SastScanResultDTO:
        if not isinstance(report, dict) or not isinstance(report.get("results"), list):
            raise ValueError("Invalid OpenGrep report: results must be a list")

        summary = SastSummaryDTO()
        findings = []
        for match in report["results"]:
            extra = match.get("extra", {})
            severity = extra.get("severity", "UNKNOWN")
            if severity not in {"ERROR", "WARNING", "INFO"}:
                severity = "UNKNOWN"
            start = match["start"]
            end = match.get("end") or {}
            finding = SastFindingDTO(
                rule_id=match["check_id"], severity=severity, message=extra.get("message", ""),
                file_path=self._relative_path(match["path"], target),
                start_line=start["line"], start_column=start.get("col"),
                end_line=end.get("line"), end_column=end.get("col"),
                metadata=extra.get("metadata") or {},
            )
            findings.append(finding)
            level = severity.lower()
            setattr(summary, level, getattr(summary, level) + 1)

        errors = [SastScanErrorDTO(
            error_type=error.get("type", "unknown"), message=error.get("message", ""),
            level=error.get("level"), code=error.get("code"),
            file_path=self._relative_path(error["path"], target) if error.get("path") else None,
        ) for error in (report.get("errors") or [])]
        scanned = report.get("paths", {}).get("scanned")
        complete = (exit_code == 0 or (exit_code == 1 and bool(findings))) and not errors and scanned != []
        return SastScanResultDTO(
            version=report.get("version"), target=str(target),
            success=exit_code == 0 and complete and summary.get_num() == 0,
            complete=complete, scanned_files=len(scanned) if scanned is not None else None,
            summary=summary, findings=findings, errors=errors, raw_report=report,
        )

    def execute(self):
        target = Path(self.config.repo_path).resolve()
        if not target.is_dir():
            raise RuntimeError(f"SAST source directory does not exist: {target}")

        fd, report_path = tempfile.mkstemp(prefix="opengrep-report-", suffix=".json")
        os.close(fd)
        try:
            command = [
                "opengrep", "scan", "--config", str(RULES_PATH),
                "--json", "--output", report_path,
                "--disable-version-check",
                "--no-git-ignore", "--x-ignore-semgrepignore-files", "--disable-nosem",
                "--no-rewrite-rule-ids", "--strict", "--error",
                "--timeout", str(self.config.sast_timeout),
                "--max-target-bytes", str(self.config.sast_max_target_bytes),
            ]
            for exclude in EXCLUDES:
                command.extend(["--exclude", exclude])
            # Tool repositories cannot suppress findings with ignore files or nosem comments.
            with tempfile.TemporaryDirectory(prefix="opengrep-work-") as work_dir:
                command.append(str(target))
                self._send_update("RUNNING", logs="Scanning FL-Net tool source with OpenGrep...", progress=10)
                return_code, _, stderr = self._run_command(command, cwd=work_dir)

            try:
                with open(report_path, encoding="utf-8") as report_file:
                    report = json.load(report_file)
                scan_result = self.parse_opengrep_result(report, target, return_code)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                raise RuntimeError(f"OpenGrep scan failed. Error: {stderr or exc}") from exc

            self.result.sast_scan_result = scan_result
            summary = scan_result.summary
            for finding in scan_result.findings:
                self._append_log(
                    f"{finding.file_path}:{finding.start_line} "
                    f"[{finding.severity}] {finding.rule_id}: {finding.message}\n"
                )

            self._send_update(
                "RUNNING", progress=95,
                logs=f"OpenGrep: {summary.error} ERROR, {summary.warning} WARNING, "
                     f"{summary.info} INFO, {summary.unknown} UNKNOWN findings.",
            )
            if return_code not in (0, 1) or scan_result.errors:
                raise RuntimeError(f"OpenGrep scan incomplete (exit code {return_code}). Errors: {scan_result.errors}. {stderr}")
            if scan_result.scanned_files == 0:
                raise RuntimeError("OpenGrep scanned no source files; SAST coverage is incomplete.")
            if summary.get_num():
                raise RuntimeError(f"OpenGrep found {summary.get_num()} SAST findings. See sastScanResult for details.")
            if return_code != 0:
                raise RuntimeError(f"OpenGrep scan failed with exit code {return_code}. Error: {stderr}")
            logger.info("OpenGrep scan completed without findings.")
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

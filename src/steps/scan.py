import json
import logging
import os
import tempfile
from typing import Dict, Any

from src.client.result_dto import VulnerabilitySummaryDTO, SecurityScanResultDTO
from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class ScanImageStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "SCAN_IMAGE"

    @property
    def allow_to_fail(self) -> bool:
        return True

    def parse_trivy_result(
            self,
            stdout: str,
            image_name: str,
            exit_code: int
    ) -> SecurityScanResultDTO:
        report = json.loads(stdout)

        summary = VulnerabilitySummaryDTO()
        reasons: Dict[str, Any] = {}

        for result in report.get("Results", []) or []:
            cls = result.get("Class", "unknown")
            typ = result.get("Type", "unknown")
            target = cls + "-" + typ
            vulns = result.get("Vulnerabilities") or []

            if not vulns:
                continue

            reasons[target] = result.get("Vulnerabilities")

            for v in vulns:
                sev = v.get("Severity", "UNKNOWN").lower()
                if hasattr(summary, sev):
                    setattr(summary, sev, getattr(summary, sev) + 1)

        result = SecurityScanResultDTO(
            tool="trivy",
            target=image_name,
            success=exit_code == 0,
            summary=summary,
            rawReport=reasons,
        )
        self.result.vulnerability_scan_result = result
        return result

    def execute(self):
        image_name = self.config.get_docker_name()
        logger.info(f"Scanning image: {image_name} for HIGH and CRITICAL vulnerabilities.")

        # write report to file
        fd, report_path = tempfile.mkstemp(prefix="trivy-report-", suffix=".json")
        os.close(fd)
        try:
            command = [
                "trivy", "image",
                "--format", "json",
                "--output", report_path,
                "--severity", "HIGH,CRITICAL",
                "--exit-code", "1",
                image_name
            ]

            self._send_update("RUNNING", logs="Starting Trivy scan...", progress=10)

            return_code, _, stderr = self._run_command(command, cwd=self.config.repo_path)

            self._send_update("RUNNING", logs="Scan command finished, processing results...",
                              progress=90)

            try:
                with open(report_path, encoding="utf-8") as report_file:
                    report = report_file.read()
                # sets the result that is uploaded with the publish summary, also for a clean scan
                scan_result = self.parse_trivy_result(report, image_name, return_code)
            except (OSError, json.JSONDecodeError):
                raise Exception(f"Trivy scan failed. Error: {stderr}")
        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

        summary = scan_result.summary
        self._send_update(
            "RUNNING",
            logs=f"Trivy: {summary.critical} critical, {summary.high} high",
            progress=95
        )

        if return_code != 0:
            raise Exception(
                f"Trivy found {summary.get_num()} HIGH/CRITICAL vulnerabilities. See logs for details.")
        logger.info("Trivy scan completed. No HIGH or CRITICAL vulnerabilities found.")

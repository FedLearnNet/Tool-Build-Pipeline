import json
import logging
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

        logger.info("Trivy scan reasons: %s", reasons)
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

        command = [
            "trivy", "image",
            "--format", "json",
            "--severity", "HIGH,CRITICAL",
            "--exit-code", "1",
            image_name
        ]

        self._send_update("RUNNING", logs="Starting Trivy scan...", progress=10)

        return_code, stdout, stderr = self._run_command(command, cwd=self.config.repo_path)

        self._send_update("RUNNING", logs="Scan command finished, processing results...",
                          progress=90)

        if return_code != 0:
            try:
                scan_result = self.parse_trivy_result(stdout, image_name, return_code)
                num_vulns = scan_result.summary.get_num() if scan_result and scan_result.summary else 0

                error_msg = f"Trivy found {num_vulns} HIGH/CRITICAL vulnerabilities. See logs for details."

                raise Exception(error_msg)
            except json.JSONDecodeError:
                raise Exception(f"Trivy scan failed. Error: {stderr}")
        else:
            logger.info("Trivy scan completed. No HIGH or CRITICAL vulnerabilities found.")

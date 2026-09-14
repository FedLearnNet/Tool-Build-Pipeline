from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field


class VulnerabilitySummaryDTO(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    unknown: int = 0

    def get_num(self):
        return self.critical + self.high + self.medium + self.low + self.unknown


class SecurityScanResultDTO(BaseModel):
    tool: str = Field(..., description="Security scanner used, e.g. trivy")
    target: str = Field(..., description="Scanned artifact, e.g. image name")
    success: bool

    summary: VulnerabilitySummaryDTO

    raw_report: Optional[Dict[str, Any]] = Field(
        alias="rawReport",
        description="Full raw scanner output (JSON)"
    )

    model_config = {
        "populate_by_name": True
    }


class MalwareFindingDTO(BaseModel):
    file_path: str = Field(..., alias="filePath")
    signature: Optional[str] = None
    raw_line: Optional[str] = None

    model_config = {"populate_by_name": True}


class MalwareScanResultDTO(BaseModel):
    tool: str = "clamav"
    success: bool
    infected_count: int = 0
    findings: List[MalwareFindingDTO] = Field(default_factory=list)


class AppPublishInfoDTO(BaseModel):
    commit_hash: Optional[str] = Field(default=None, alias="commitHash")
    file_paths: Optional[List[str]] = Field(default=None, alias="filePaths")  # raw git file links
    vulnerability_scan_result: Optional[SecurityScanResultDTO] = Field(
        default=None, alias="vulnerabilityScanResult"
    )
    malware_scan_result: Optional[MalwareScanResultDTO] = Field(
        default=None, alias="malwareScanResult"
    )
    image_name: Optional[str] = Field(default=None, alias="imageName")

    model_config = {
        "populate_by_name": True
    }

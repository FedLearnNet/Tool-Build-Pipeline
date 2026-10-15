from typing import Dict, Any, List, Literal, Optional

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


class SastSummaryDTO(BaseModel):
    error: int = 0
    warning: int = 0
    info: int = 0
    unknown: int = 0

    def get_num(self) -> int:
        return self.error + self.warning + self.info + self.unknown


class SastFindingDTO(BaseModel):
    rule_id: str = Field(alias="ruleId")
    severity: Literal["ERROR", "WARNING", "INFO", "UNKNOWN"]
    message: str
    file_path: str = Field(alias="filePath")
    start_line: int = Field(alias="startLine", ge=1)
    end_line: Optional[int] = Field(default=None, alias="endLine", ge=1)
    start_column: Optional[int] = Field(default=None, alias="startColumn", ge=1)
    end_column: Optional[int] = Field(default=None, alias="endColumn", ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class SastScanErrorDTO(BaseModel):
    error_type: str = Field(alias="type")
    message: str = ""
    level: Optional[str] = None
    code: Optional[int] = None
    file_path: Optional[str] = Field(default=None, alias="filePath")

    model_config = {"populate_by_name": True}


class SastScanResultDTO(BaseModel):
    tool: str = "opengrep"
    version: Optional[str] = None
    target: str
    success: bool
    complete: bool = Field(description="False when scanning failed, was partial, or scanned no files")
    scanned_files: Optional[int] = Field(default=None, alias="scannedFiles", ge=0)
    summary: SastSummaryDTO
    findings: List[SastFindingDTO] = Field(default_factory=list)
    errors: List[SastScanErrorDTO] = Field(default_factory=list)
    raw_report: Optional[Dict[str, Any]] = Field(default=None, alias="rawReport")

    model_config = {"populate_by_name": True}


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
    sast_scan_result: Optional[SastScanResultDTO] = Field(
        default=None, alias="sastScanResult"
    )
    malware_scan_result: Optional[MalwareScanResultDTO] = Field(
        default=None, alias="malwareScanResult"
    )
    image_name: Optional[str] = Field(default=None, alias="imageName")

    model_config = {
        "populate_by_name": True
    }

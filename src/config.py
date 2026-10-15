from enum import Enum
from typing import Optional, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.client.dto import PipelineRunInfoDTO


class RunMode(str, Enum):
    LOCAL_BUILD = "LOCAL_BUILD"
    ALL = "ALL"
    SCAN_ONLY = "SCAN_ONLY"


class AppConfig(BaseSettings):
    pipeline_id: str = Field(default="")
    pipeline_secret: str = Field(default="")
    oauth_token: str = Field(default="")
    pipeline_api_key: str = Field(default="")

    use_buildx: bool = Field(default=True)
    buildx_platforms: List[str] = Field(
        default_factory=lambda: ["linux/arm64/v8", "linux/amd64"]
    )
    buildx_sbom: bool = Field(default=True)
    buildx_provenance_mode: Optional[str] = Field(default="max")
    cosign_sign: bool = Field(default=False)
    cosign_key: Optional[str] = Field(default=None)
    docker_login: bool = Field(default=False)

    http_url: str = Field(default="http://localhost:8080")
    docker_registry: str = Field(default="ghcr.io")

    run_mode: RunMode = Field(default=RunMode.ALL)
    docker_group: str = Field(default="/fedlearnnet/tool-build-pipeline/pipeline")
    docker_username: str = Field(default="USERNAME")
    docker_password: str = Field(default="")
    docker_tag: str = Field(default="latest")

    repo_path: str = Field(default="./repo")
    remote_info: Optional[PipelineRunInfoDTO] = Field(default=None)

    sast_timeout: int = Field(default=30, ge=1)
    sast_max_target_bytes: int = Field(default=1_000_000, ge=1)

    model_config = SettingsConfigDict(
        env_nested_delimiter='__',
        env_file='.env',
        env_file_encoding='utf-8',
        protected_namespaces=()
    )

    @property
    def is_local_build(self) -> bool:
        return self.run_mode == RunMode.LOCAL_BUILD

    @property
    def is_scan_only(self) -> bool:
        return self.run_mode == RunMode.SCAN_ONLY

    def get_scan_tag(self) -> str:
        tag = self.remote_info.docker_tag if self.remote_info else None
        if not tag and "docker_tag" in self.model_fields_set:
            tag = self.docker_tag
        if not tag or not tag.strip():
            raise ValueError("SCAN_ONLY requires dockerTag from the API or an explicit DOCKER_TAG.")
        return tag.strip()

    def set_docker_tag(self, docker_tag: str) -> None:
        if not docker_tag:
            raise ValueError("Docker tag must not be empty.")
        self.docker_tag = docker_tag

    def get_docker_name(self) -> str:
        if not self.remote_info:
            raise ValueError("Remote info is not set in the configuration.")
        image_name = self.remote_info.image_name.lower()
        registry = self.docker_registry.removeprefix("https://").removeprefix("http://").rstrip("/")
        group = self.docker_group.strip("/")
        repository = "/".join(part for part in [registry, group, image_name] if part)
        if self.is_local_build:
            return f"{image_name}:{self.remote_info.docker_tag or self.docker_tag or 'latest'}"
        if self.is_scan_only:
            return f"{repository}:{self.get_scan_tag()}"
        return f"{repository}:{self.docker_tag}"


def load_config() -> AppConfig:
    return AppConfig()

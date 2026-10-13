from typing import Optional, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.client.dto import PipelineRunInfoDTO


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

    docker_group: str = Field(default="/fedlearnnet/tool-build-pipeline/pipeline")
    docker_username: str = Field(default="USERNAME")
    docker_password: str = Field(default="")
    docker_tag: str = Field(default="latest")

    repo_path: str = Field(default="./repo")
    remote_info: Optional[PipelineRunInfoDTO] = Field(default=None)

    model_config = SettingsConfigDict(
        env_nested_delimiter='__',
        env_file='.env',
        env_file_encoding='utf-8',
        protected_namespaces=()
    )

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
        return f"{repository}:{self.docker_tag}"


def load_config() -> AppConfig:
    return AppConfig()

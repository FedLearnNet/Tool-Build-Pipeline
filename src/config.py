from typing import Optional, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.client.dto import PipelineRunInfoDTO


class AppConfig(BaseSettings):
    pipeline_id: str = Field(default="")
    pipeline_secret: str = Field(default="")
    oauth_token: str = Field(default="")

    use_buildx: bool = Field(default=True)
    buildx_platforms: List[str] = Field(
        default_factory=lambda: ["linux/arm64/v8", "linux/amd64"]
    )
    buildx_sbom: bool = Field(default=True)
    buildx_provenance_mode: Optional[str] = Field(default="max")
    cosign_sign: bool = Field(default=False)
    docker_login: bool = Field(default=False)

    http_url: str = Field(default="http://localhost:8080")
    docker_registry: str = Field(default="gitlab.cosy.bio:5050")

    docker_group: str = Field(default="/cosybio/federated-learning/federated_db/app-build-pipeline")
    docker_username: str = Field(default="USERNAME")
    docker_password: str = Field(default="")

    repo_token: str = Field(default="")
    repo_path: str = Field(default="./repo")
    remote_info: Optional[PipelineRunInfoDTO] = Field(default=None)

    model_config = SettingsConfigDict(
        env_nested_delimiter='__',
        env_file='.env',
        env_file_encoding='utf-8',
        protected_namespaces=()
    )

    def get_docker_name(self) -> str:
        if not self.remote_info:
            raise ValueError("Remote info is not set in the configuration.")
        image_name = self.remote_info.image_name.lower()
        return f"{self.docker_registry}{self.docker_group}/{image_name}:{self.remote_info.docker_tag}"


def load_config() -> AppConfig:
    return AppConfig()

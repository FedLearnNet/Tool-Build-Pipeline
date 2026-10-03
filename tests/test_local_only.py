import io
import zipfile
from unittest.mock import MagicMock

from src.client.dto import PipelineRunInfoDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.pipeline import Pipeline
from src.steps.fetch_files import FetchFilesStep


def _config(tmp_path, **kwargs) -> AppConfig:
    return AppConfig(local_only=True, repo_path=str(tmp_path / "repo"),
                     remote_info=PipelineRunInfoDTO(image_name="fl-net/code/Double-1", docker_tag="abc123"), **kwargs)


def test_local_pipeline_skips_clone_and_push(tmp_path) -> None:
    steps = [step.step_name for step in Pipeline(_config(tmp_path), MagicMock()).steps]
    assert steps == ["FETCH_CONFIG", "FETCH_FILES", "BUILD_IMAGE", "SCAN_IMAGE", "MALWARE_CHECK",
                     "RUN_PYTEST", "COLLECT_SUMMARY"]


def test_local_image_has_no_registry(tmp_path) -> None:
    assert _config(tmp_path).get_docker_name() == "fl-net/code/double-1:abc123"


def test_local_files_are_the_build_context(tmp_path) -> None:
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "stale.py").write_text("old")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("Dockerfile", "FROM base\n")
    client = MagicMock(get_zip_for_pipeline=MagicMock(return_value=buffer.getvalue()))
    FetchFilesStep(_config(tmp_path), client, AppPublishInfoDTO()).execute()
    assert [p.name for p in (tmp_path / "repo").iterdir()] == ["Dockerfile"]

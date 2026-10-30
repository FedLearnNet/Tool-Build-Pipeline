from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.client.dto import PipelineRunInfoDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig, RunMode
from src.pipeline import Pipeline
from src.steps.collect_summary import CollectSummaryStep
from src.steps.pull import PullImageStep


def test_default_mode_preserves_remote_builds():
    config = AppConfig(_env_file=None)
    assert config.run_mode == RunMode.ALL
    assert [step.step_name for step in Pipeline(config, MagicMock()).steps] == [
        "FETCH_CONFIG", "CLONE_REPO", "FETCH_FILES", "SAST", "BUILD_IMAGE",
        "SCAN_IMAGE", "MALWARE_CHECK", "RUN_PYTEST", "PUSH_IMAGE", "COLLECT_SUMMARY",
    ]


def test_run_mode_from_environment(monkeypatch):
    monkeypatch.setenv("RUN_MODE", "SCAN_ONLY")
    assert AppConfig(_env_file=None).is_scan_only


def test_run_mode_from_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("RUN_MODE=SCAN_ONLY\n")
    assert AppConfig(_env_file=env_file).is_scan_only


def test_invalid_run_mode_is_rejected():
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None, run_mode="typo")


def scan_config(**kwargs):
    return AppConfig(
        _env_file=None, run_mode=RunMode.SCAN_ONLY,
        docker_registry="https://registry.example.com/", docker_group="/team/apps/",
        remote_info=PipelineRunInfoDTO(imageName="Demo", dockerTag="published-commit"),
        **kwargs,
    )


def test_scan_only_has_no_source_build_test_or_publish_steps():
    assert [step.step_name for step in Pipeline(scan_config(), MagicMock()).steps] == [
        "FETCH_CONFIG", "PULL_IMAGE", "SCAN_IMAGE", "COLLECT_SUMMARY",
    ]


def test_scan_only_uses_published_tag_instead_of_default_or_new_commit():
    config = scan_config(docker_tag="different-tag")
    assert config.get_docker_name() == "registry.example.com/team/apps/demo:published-commit"


def test_scan_only_requires_an_explicit_existing_tag():
    config = scan_config()
    config.remote_info.docker_tag = None
    with pytest.raises(ValueError, match="SCAN_ONLY requires dockerTag"):
        config.get_docker_name()
    config.set_docker_tag("existing-tag")
    assert config.get_docker_name().endswith(":existing-tag")
    config.set_docker_tag("latest")
    assert config.get_docker_name().endswith(":latest")


def test_pull_always_refreshes_existing_image_and_fails_on_missing_image():
    config = scan_config()
    step = PullImageStep(config, MagicMock(), AppPublishInfoDTO())
    step._run_command = MagicMock(return_value=(1, "", "manifest unknown"))
    with pytest.raises(RuntimeError, match="Docker pull failed.*manifest unknown"):
        step.execute()
    step._run_command.assert_called_once_with(["docker", "pull", config.get_docker_name()])


def test_pull_private_image_logs_in_without_password_in_argv(monkeypatch):
    login = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("src.steps.pull.subprocess.run", login)
    config = scan_config(docker_login=True, docker_username="user", docker_password="a-secret")
    step = PullImageStep(config, MagicMock(), AppPublishInfoDTO())
    step._run_command = MagicMock(return_value=(0, "", ""))
    step.execute()
    assert "--password-stdin" in login.call_args.args[0]
    assert "a-secret" not in login.call_args.args[0]
    assert login.call_args.kwargs["input"] == "a-secret"


def test_rescan_summary_omits_source_and_other_scan_metadata():
    config = scan_config(repo_path="/does/not/exist")
    result = AppPublishInfoDTO()
    client = MagicMock()
    CollectSummaryStep(config, client, result).execute()
    assert result.model_dump(by_alias=True, exclude_none=True) == {"imageName": config.get_docker_name()}
    client.upload_summary.assert_called_once_with(result)

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.client.dto import PipelineRunInfoDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.steps.push import PushImageStep
from src.steps.collect_summary import CollectSummaryStep

DIGEST = "sha256:" + "a" * 64
IMAGE_REF = "registry.example.com/team/apps/demo-app@" + DIGEST


class DummyApiClient:
    def __init__(self):
        self.updates = []

    def send_status_update(self, payload):
        self.updates.append(payload)


class RecordingPushImageStep(PushImageStep):
    def __init__(self, config, api_client, result):
        super().__init__(config, api_client, result)
        self.commands = []
        self.cosign_exit_code = 0
        self.digest = DIGEST

    def _run_command(self, command, cwd=".", env=None):
        self.commands.append(command)

        if command[:3] == ["docker", "buildx", "version"]:
            return 0, "", ""
        if command[:3] == ["docker", "context", "inspect"]:
            return 1, "", "not found"
        if command[:3] == ["docker", "context", "create"]:
            return 0, "", ""
        if command[:4] == ["docker", "buildx", "inspect", self.builder_name]:
            return 1, "", "not found"
        if command[:3] == ["docker", "buildx", "inspect"] and "--builder" in command:
            return 0, "", ""
        if command[:3] == ["docker", "buildx", "create"]:
            return 0, "", ""
        if command[:3] == ["docker", "buildx", "build"]:
            if "--metadata-file" in command:
                Path(command[command.index("--metadata-file") + 1]).write_text(
                    json.dumps({"containerimage.digest": self.digest}), encoding="utf-8"
                )
            return 0, "", ""
        if command[:4] == ["docker", "buildx", "rm", "-f"]:
            return 0, "", ""
        if command[:4] == ["docker", "context", "rm", "-f"]:
            return 0, "", ""
        if command[:2] == ["docker", "push"]:
            return 0, f"1.2.3: digest: {self.digest} size: 1234\n", ""
        if command[:2] == ["cosign", "version"]:
            return 0, "", ""
        if command[:3] == ["cosign", "sign", "--yes"]:
            return self.cosign_exit_code, "", "signing failed"

        raise AssertionError(f"Unexpected command: {command}")


def make_config(**overrides) -> AppConfig:
    config = AppConfig(
        repo_path="/tmp/repo",
        docker_registry="registry.example.com",
        docker_group="/team/apps",
        remote_info=PipelineRunInfoDTO(
            imageName="demo-app",
            gitRepoUrl="https://example.com/repo.git",
            dockerTag="1.2.3",
        ),
        **overrides,
    )
    return config


def test_push_step_buildx_adds_sbom_and_provenance_flags():
    step = RecordingPushImageStep(make_config(), DummyApiClient(), AppPublishInfoDTO())

    step.execute()

    build_commands = [command for command in step.commands if command[:3] == ["docker", "buildx", "build"]]
    assert len(build_commands) == 1

    build_command = build_commands[0]
    assert "--push" in build_command
    assert "--sbom=true" in build_command
    assert "--provenance=mode=max" in build_command
    assert build_command[-1] == "/tmp/repo"


def test_push_step_can_sign_pushed_image_with_cosign():
    step = RecordingPushImageStep(
        make_config(use_buildx=False, cosign_sign=True, cosign_key="hashivault://release"),
        DummyApiClient(),
        AppPublishInfoDTO(),
    )

    step.execute()

    assert ["docker", "push", "registry.example.com/team/apps/demo-app:1.2.3"] in step.commands
    assert ["cosign", "version"] in step.commands
    assert ["cosign", "sign", "--yes", "--key", "hashivault://release", IMAGE_REF] in step.commands
    assert step.result.image_name == IMAGE_REF


def test_signed_buildx_uses_the_published_index_digest():
    step = RecordingPushImageStep(
        make_config(cosign_sign=True, cosign_key="hashivault://release"), DummyApiClient(), AppPublishInfoDTO()
    )

    step.execute()

    assert ["cosign", "sign", "--yes", "--key", "hashivault://release", IMAGE_REF] in step.commands
    assert step.result.image_name == IMAGE_REF


def test_signing_requires_a_key_before_pushing():
    step = RecordingPushImageStep(make_config(cosign_sign=True), DummyApiClient(), AppPublishInfoDTO())

    with pytest.raises(Exception, match="requires COSIGN_KEY"):
        step.execute()

    assert step.commands == []


@pytest.mark.parametrize("use_buildx", [True, False])
def test_invalid_push_digest_cannot_be_signed(use_buildx):
    step = RecordingPushImageStep(
        make_config(use_buildx=use_buildx, cosign_sign=True, cosign_key="hashivault://release"),
        DummyApiClient(), AppPublishInfoDTO()
    )
    step.digest = "sha256:invalid"

    with pytest.raises(Exception, match="valid registry manifest digest"):
        step.execute()

    assert not any(command[:2] == ["cosign", "sign"] for command in step.commands)
    assert step.result.image_name is None


def test_cosign_failure_does_not_publish_a_reference():
    step = RecordingPushImageStep(
        make_config(cosign_sign=True, cosign_key="hashivault://release"), DummyApiClient(), AppPublishInfoDTO()
    )
    step.cosign_exit_code = 1

    with pytest.raises(Exception, match="Cosign signing failed"):
        step.execute()

    assert step.result.image_name is None


def test_summary_keeps_the_signed_digest(tmp_path):
    config = make_config()
    config.repo_path = str(tmp_path)
    result = AppPublishInfoDTO(imageName=IMAGE_REF)
    step = CollectSummaryStep(config, MagicMock(), result)
    step._get_commit_hash = lambda: "commit"

    step.execute()

    assert step.api_client.upload_summary.call_args.args[0].image_name == IMAGE_REF

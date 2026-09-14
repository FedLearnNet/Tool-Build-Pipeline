from src.client.dto import PipelineRunInfoDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.steps.push import PushImageStep


class DummyApiClient:
    def __init__(self):
        self.updates = []

    def send_status_update(self, payload):
        self.updates.append(payload)


class RecordingPushImageStep(PushImageStep):
    def __init__(self, config, api_client, result):
        super().__init__(config, api_client, result)
        self.commands = []

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
            return 0, "", ""
        if command[:4] == ["docker", "buildx", "rm", "-f"]:
            return 0, "", ""
        if command[:4] == ["docker", "context", "rm", "-f"]:
            return 0, "", ""
        if command[:2] == ["docker", "push"]:
            return 0, "", ""
        if command[:2] == ["cosign", "version"]:
            return 0, "", ""
        if command[:3] == ["cosign", "sign", "--yes"]:
            return 0, "", ""

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
        make_config(use_buildx=False, cosign_sign=True),
        DummyApiClient(),
        AppPublishInfoDTO(),
    )

    step.execute()

    assert ["docker", "push", "registry.example.com/team/apps/demo-app:1.2.3"] in step.commands
    assert ["cosign", "version"] in step.commands
    assert ["cosign", "sign", "--yes", "registry.example.com/team/apps/demo-app:1.2.3"] in step.commands

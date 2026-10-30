import io

from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.steps import base
from src.steps.base import BaseStep


class RecordingApiClient:
    def __init__(self):
        self.updates = []

    def send_status_update(self, update_dto):
        self.updates.append(update_dto)


class DummyStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "BUILD_IMAGE"

    def execute(self):
        return None


def make_step() -> tuple[DummyStep, RecordingApiClient]:
    client = RecordingApiClient()
    return DummyStep(AppConfig(), client, AppPublishInfoDTO()), client


def test_command_output_is_sent_in_batches_and_completely():
    step, client = make_step()
    lines = [f"line {i}\n" for i in range(500)]

    step._stream_reader(io.StringIO("".join(lines)), [])
    step._send_update("SUCCESS", "done", progress=100)

    assert len(client.updates) < 10
    assert "".join(u.logs or "" for u in client.updates) == "".join(lines) + "done"
    assert client.updates[-1].status == "SUCCESS"


def test_output_is_flushed_once_the_interval_passed(monkeypatch):
    step, client = make_step()
    monkeypatch.setattr(base, "LOG_FLUSH_INTERVAL_SECONDS", 0)

    step._stream_reader(io.StringIO("first\nsecond\n"), [])

    assert [u.logs for u in client.updates] == ["first\n", "second\n"]

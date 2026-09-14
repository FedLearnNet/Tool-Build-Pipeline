import base64
import uuid
from typing import Dict, List

from src.client.dto import FileDTO, PipelineRunInfoDTO, StatusUpdateDTO
from src.client.result_dto import AppPublishInfoDTO


class ApiRecorder:
    def __init__(self, info: PipelineRunInfoDTO, files: List[FileDTO]):
        self.info = info
        self.files = files
        self.updates: List[StatusUpdateDTO] = []

    def send_status_update(self, payload: StatusUpdateDTO):
        self.updates.append(payload)

    def get_pipeline_info(self) -> PipelineRunInfoDTO:
        return self.info

    def get_files_to_inject(self) -> List[FileDTO]:
        return self.files

    def upload_summary(self, result: AppPublishInfoDTO):
        print(result.model_dump_json(indent=2))

    def check_updates(self):

        statuses = [u.status for u in self.updates if getattr(u, "status", None) is not None]
        assert "FAILED" not in statuses, f"Found FAILED in status updates: {self.updates}"

        grouped = _group_updates_by_step(self.updates)

        for step, st_list in grouped.items():
            assert st_list[
                       0] == "RUNNING", f"{step}: first status should be RUNNING, got {st_list[0]}"

        must_succeed = [
            "FETCH_CONFIG",
            "CLONE_REPO",
            "FETCH_FILES",
            "BUILD_IMAGE",
            "MALWARE_CHECK",
            "RUN_PYTEST",
            "PUSH_IMAGE",
            "COLLECT_SUMMARY",
        ]

        for step in must_succeed:
            assert step in grouped, f"Missing status updates for step {step}. Updates: {grouped.keys()}"
            assert "SUCCESS" in grouped[step], f"{step}: expected SUCCESS, got {grouped[step]}"

        scan_step = "SCAN_IMAGE"
        if scan_step in grouped:
            assert grouped[scan_step][0] == "RUNNING"
            assert any(s in ("WARNING", "SUCCESS") for s in grouped[scan_step]), \
                f"{scan_step}: expected WARNING or SUCCESS, got {grouped[scan_step]}"


def _group_updates_by_step(updates: List[StatusUpdateDTO]) -> Dict[str, List[str]]:
    """Group status updates by step.

    `ApiRecorder.updates` stores `StatusUpdateDTO` pydantic models (not dicts),
    so we use attribute access.
    """
    grouped: Dict[str, List[str]] = {}
    for u in updates:
        step = getattr(u, "step_name", None)
        status = getattr(u, "status", None)
        if not step or not status:
            continue
        grouped.setdefault(step, []).append(status)
    return grouped


def get_api_recorder(
        origin_url="https://gitlab.cosy.bio/cosybio/federated-learning/federated_db/apps/train-test-split.git"):
    injected_test_py = (
        "def test_injected_pytest_runs():\n"
        "    assert 1 + 1 == 2\n"
    )
    files_payload = [
        FileDTO(
            filePath="test.py",
            content=base64.b64encode(injected_test_py.encode("utf-8")).decode("ascii"),
        )
    ]
    test_image_name = uuid.uuid4().hex + "-test-image"
    info_payload = PipelineRunInfoDTO(imageName=test_image_name, gitRepoUrl=origin_url,
                                      dockerTag="test")

    return ApiRecorder(info=info_payload, files=[])


def print_banner_mocked(name: str):
    print("=" * 60)
    print("= MOCK MODE")
    print("= " + name)
    print("=" * 60)

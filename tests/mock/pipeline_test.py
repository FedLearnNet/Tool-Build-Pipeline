import logging

from src.client.client import ApiClient
from src.config import AppConfig
from src.pipeline import Pipeline
from src.steps.build import BuildImageStep
from src.steps.clone import CloneRepoStep
from src.steps.collect_summary import CollectSummaryStep
from src.steps.fetch_config import FetchConfigStep
from src.steps.fetch_files import FetchFilesStep
from src.steps.test import RunPytestStep
from tests.mock.malware_mock import MalwareCheckStepMock
from tests.mock.push_mock import PushImageStepMock
from tests.mock.scan_mock import ScanImageStepMock

logger = logging.getLogger(__name__)


class TestPipeline(Pipeline):
    def __init__(self, config: AppConfig, client: ApiClient):
        super().__init__(config, client)
        self.steps = [
            FetchConfigStep(config, client, self.result),
            CloneRepoStep(config, client, self.result),
            FetchFilesStep(config, client, self.result),
            BuildImageStep(config, client, self.result),
            ScanImageStepMock(config, client, self.result),
            MalwareCheckStepMock(config, client, self.result),
            RunPytestStep(config, client, self.result),
            PushImageStepMock(config, client, self.result),
            CollectSummaryStep(config, client, self.result),
        ]

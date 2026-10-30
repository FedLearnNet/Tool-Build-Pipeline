import logging

from src.client.client import ApiClient
from src.config import AppConfig
from src.pipeline import Pipeline
from src.steps.malware import MalwareCheckStep
from src.steps.push import PushImageStep
from src.steps.sast import SastStep
from src.steps.scan import ScanImageStep
from tests.mock.malware_mock import MalwareCheckStepMock
from tests.mock.push_mock import PushImageStepMock
from tests.mock.scan_mock import ScanImageStepMock
from tests.mock.sast_mock import SastStepMock

logger = logging.getLogger(__name__)


class TestPipeline(Pipeline):
    __test__ = False

    def __init__(self, config: AppConfig, client: ApiClient):
        super().__init__(config, client)
        mocks = {SastStep: SastStepMock, ScanImageStep: ScanImageStepMock,
                 MalwareCheckStep: MalwareCheckStepMock, PushImageStep: PushImageStepMock}
        self.steps = [mocks[type(step)](config, client, self.result) if type(step) in mocks else step
                      for step in self.steps]

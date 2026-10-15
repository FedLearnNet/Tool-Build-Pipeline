from src.steps.sast import SastStep
from tests.mock.helper import print_banner_mocked


class SastStepMock(SastStep):
    def execute(self):
        print_banner_mocked("SastStep")

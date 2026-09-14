import logging

from src.steps.scan import ScanImageStep
from tests.mock.helper import print_banner_mocked

logger = logging.getLogger(__name__)


class ScanImageStepMock(ScanImageStep):

    def execute(self):
        print_banner_mocked("ScanImageStep")

        image_name = self.config.get_docker_name()

        logger.info(f"Scanning image: {image_name} for HIGH and CRITICAL vulnerabilities.")

        logger.info(
            f"Scanning image: {image_name} for HIGH and CRITICAL vulnerabilities. DONE MOCK")

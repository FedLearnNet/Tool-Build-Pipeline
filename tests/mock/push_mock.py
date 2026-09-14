import logging

from src.steps.push import PushImageStep
from tests.mock.helper import print_banner_mocked

logger = logging.getLogger(__name__)


class PushImageStepMock(PushImageStep):
    def execute(self):
        print_banner_mocked("PushImageStep")
        image_name = self.config.get_docker_name()

        logger.info(f"Pushing image: {image_name} to registry.")

        logger.info("Image pushed successfully.")

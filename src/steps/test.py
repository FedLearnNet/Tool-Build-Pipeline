import logging
import os
from pathlib import Path
from typing import Mapping

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class RunPytestStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "RUN_PYTEST"

    @property
    def allow_to_fail(self) -> bool:
        return True

    def execute(self):
        image_name = self.config.get_docker_name()

        logger.info(f"Running tests inside Docker image: {image_name}")
        command = [
            "docker",
            "run",
            "--rm",
            "-e",
            "TEST_MODE=true",
            "-e",
            "PYTHONUNBUFFERED=1",
            image_name,
            "python",
            "-m",
            "main",
        ]

        logger.info("Running command: " + " ".join(command))
        return_code, stdout, stderr = self._run_command(command)

        if return_code != 0:
            raise Exception(f"Container test run failed.\n{stdout}\n{stderr}".strip())

        logger.info("Container test run passed.")

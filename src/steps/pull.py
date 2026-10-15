import logging
import subprocess

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class PullImageStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "PULL_IMAGE"

    def execute(self):
        image_name = self.config.get_docker_name()
        if self.config.docker_login and self.config.docker_password:
            process = subprocess.run(
                ["docker", "login", "--username", self.config.docker_username,
                 "--password-stdin", self.config.docker_registry],
                input=self.config.docker_password,
                text=True,
                capture_output=True,
                check=False,
            )
            if process.returncode != 0:
                raise RuntimeError(f"Docker login failed. Error: {process.stderr}")

        logger.info("Pulling published image for vulnerability rescan: %s", image_name)
        self._send_update("RUNNING", logs=f"Pulling existing image: {image_name}", progress=10)
        return_code, _, stderr = self._run_command(["docker", "pull", image_name])
        if return_code != 0:
            raise RuntimeError(f"Docker pull failed for {image_name}. Error: {stderr}")

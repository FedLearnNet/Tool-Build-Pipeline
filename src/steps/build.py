import logging
import os

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class BuildImageStep(BaseStep):

    @property
    def step_name(self) -> str:
        return "BUILD_IMAGE"

    def docker_login(self):
        docker_user = self.config.docker_username
        docker_password = self.config.docker_password
        if docker_password:
            logger.info(f"Logging into Docker registry: {self.config.docker_registry}")
            command = [
                "docker", "login",
                "-u", docker_user,
                "-p", docker_password,
                self.config.docker_registry
            ]

            return_code, _, stderr = self._run_command(command)
            if return_code != 0:
                raise Exception(f"Docker login failed. Error: {stderr}")
            logger.info("Docker login successful.")
        else:
            logger.warning("Registry credentials not provided; skipping Docker login.")

    def execute(self):
        logger.info(f"Starting Docker image build for: {self.config.remote_info.image_name}")
        logger.info(f"Build context path: {self.config.repo_path}")

        if self.config.docker_login:
            self.docker_login()

        image_name = self.config.get_docker_name()
        self._send_update("RUNNING", logs="Building Docker image without buildx for current platform")
        command = [
            "docker", "build",
            "-t", image_name,
            "--progress=plain",
            self.config.repo_path
        ]
        run_env = os.environ.copy()
        run_env["DOCKER_BUILDKIT"] = "1"
        run_env["BUILDKIT_PROGRESS"] = "plain"

        return_code, _, stderr = self._run_command(command, env=run_env)

        if return_code != 0:
            raise Exception(f"Docker build failed with exit code {return_code}. Error: {stderr}")

        logger.info("Docker image built successfully.")

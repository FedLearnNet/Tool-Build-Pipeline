import logging
import shutil
from src.steps.base import BaseStep

logger = logging.getLogger(__name__)

class CloneRepoStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "CLONE_REPO"

    def execute(self):
        logger.info(f"Cleaning up work directory: {self.config.repo_path}")
        # Clean up the directory before cloning
        shutil.rmtree(self.config.repo_path, ignore_errors=True)
        git_repo_url = self.config.remote_info.git_repo_url
        logger.info(f"Cloning repository from {git_repo_url} into {self.config.repo_path}")
        token = self.config.repo_token
        username = self.config.docker_username
        if git_repo_url.startswith("https://gitlab.cosy.bio"):
            command = ["git", "clone",
                       f"https://{username}:{token}@{git_repo_url[8:]}", self.config.repo_path]
        else:
            command = ["git", "clone", git_repo_url, self.config.repo_path]
        return_code, _, stderr = self._run_command(command)

        if return_code != 0:
            raise Exception(f"Git clone failed. Error: {stderr}")

        logger.info("Repository cloned successfully.")


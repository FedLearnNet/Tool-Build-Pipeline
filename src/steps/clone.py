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
        command = ["git", "clone", git_repo_url, self.config.repo_path]
        return_code, _, stderr = self._run_command(command)

        if return_code != 0:
            raise Exception(f"Git clone failed. Error: {stderr}")

        return_code, stdout, stderr = self._run_command(
            ["git", "rev-parse", "HEAD"], cwd=self.config.repo_path
        )
        commit_hash = (stdout or "").strip()
        if return_code != 0 or not commit_hash:
            raise Exception(f"Failed to read commit hash: {stderr}")

        self.result.commit_hash = commit_hash
        self.config.set_docker_tag(commit_hash)
        logger.info(f"Repository cloned successfully at commit: {commit_hash}")

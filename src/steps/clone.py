import logging
import re
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

        requested_commit = self.config.remote_info.commit_hash
        if requested_commit:
            if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", requested_commit):
                raise ValueError("A full Git commit hash is required")
            return_code, _, stderr = self._run_command(
                ["git", "checkout", "--detach", requested_commit], cwd=self.config.repo_path
            )
            if return_code != 0:
                raise Exception(f"Failed to check out commit {requested_commit}: {stderr}")

        return_code, stdout, stderr = self._run_command(
            ["git", "rev-parse", "HEAD"], cwd=self.config.repo_path
        )
        commit_hash = (stdout or "").strip()
        if return_code != 0 or not commit_hash:
            raise Exception(f"Failed to read commit hash: {stderr}")
        if requested_commit and commit_hash.lower() != requested_commit.lower():
            raise Exception(f"Checked out commit {commit_hash} does not match {requested_commit}")

        self.result.commit_hash = commit_hash
        self.config.set_docker_tag(commit_hash)
        logger.info(f"Repository cloned successfully at commit: {commit_hash}")

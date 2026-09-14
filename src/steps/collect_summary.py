import logging
import os
from typing import List
from urllib.parse import quote

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class CollectSummaryStep(BaseStep):
    @property
    def step_name(self) -> str:
        return "COLLECT_SUMMARY"

    def _get_commit_hash(self) -> str:
        cmd = ["git", "rev-parse", "HEAD"]
        code, out, err = self._run_command(cmd, cwd=self.config.repo_path)
        if code != 0:
            raise Exception(f"Failed to read commit hash: {err}")
        return (out or "").strip()

    def _repo_base_url(self) -> str:
        url = (self.config.remote_info.git_repo_url or "").strip()
        if url.endswith(".git"):
            url = url[:-4]
        return url

    def _file_to_raw_git_link(self, commit: str, abs_path: str) -> str:
        base = self._repo_base_url()

        repo_root = os.path.abspath(self.config.repo_path)
        p = os.path.abspath(abs_path)

        if p.startswith(repo_root + os.sep):
            rel = p[len(repo_root) + 1:]
        else:
            return abs_path

        if "gitlab" in base:
            rel_q = quote(rel)
            return f"{base}/-/blob/{commit}/{rel_q}"

        rel_q = quote(rel)
        return f"{base}/blob/{commit}/{rel_q}"

    def execute(self):
        if not self.config.remote_info:
            raise Exception("remote_info missing; FetchConfigStep must run first.")

        self.result.commit_hash = self._get_commit_hash()

        base_dir = os.path.abspath(self.config.repo_path)

        logger.info("Collecting file paths from repo at commit: " + self.result.commit_hash)
        # load .env in data_dir to get correct folder if empty take "data" as default
        env_path = os.path.join(base_dir, ".env")
        data_dir = os.path.join(base_dir, "data")
        logger.info("Searching for data directory in .env file at: " + env_path)
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("DATA_DIR="):
                        data_dir = os.path.join(base_dir, line[len("DATA_DIR="):].strip())
                        break
        logger.info(f"Data dir: {data_dir}")
        file_links: List[str] = []

        for root, _, files in os.walk(data_dir):
            for fn in files:
                abs_fp = os.path.join(root, fn)
                file_links.append(self._file_to_raw_git_link(self.result.commit_hash, abs_fp))

        self.result.file_paths = file_links
        self.result.image_name = self.config.get_docker_name()
        summary_msg = "Publish summary built: " \
                      f"commit={self.result.commit_hash}, " \
                      f"files={len(self.result.file_paths)}, " \
                      f"vuln='{self.result.vulnerability_scan_result}', " \
                      f"malware='{self.result.malware_scan_result}', " \
                      f"imageName='{self.result.image_name}', "
        logger.info(summary_msg)

        self._send_update("RUNNING", logs=summary_msg, progress=90)

        self.api_client.upload_summary(self.result)

        self._send_update("SUCCESS", logs="Publish summary uploaded.", progress=100)

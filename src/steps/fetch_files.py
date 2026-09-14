import io
import logging
import base64
import os
import zipfile
from pathlib import Path
from typing import Optional

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class FetchFilesStep(BaseStep):
    """ Fetches and writes files from the server into the workspace. """

    @property
    def step_name(self) -> str:
        return "FETCH_FILES"

    def execute(self):
        """
        Fetches files from the API, decodes them, and writes them to the local workspace.
        """
        logger.info("Fetching files to inject from the server...")

        self._send_update("RUNNING", "Step Load zip.", progress=1)
        zip_bytes: Optional[bytes]  = self.api_client.get_zip_for_pipeline()
        self._send_update("RUNNING", "Zip loaded.", progress=40)

        if not zip_bytes or len(zip_bytes) == 0:
            logger.info("No files to inject.")
            self._send_update("RUNNING", "No files to inject", progress=50)
            return

        repo_path = Path(self.config.repo_path).expanduser().resolve()
        model_dir_rel = self._read_env_value(repo_path / ".env", "MODEL_DIR") or "./model"
        target_dir = self._safe_join(repo_path, model_dir_rel)
        target_dir.mkdir(parents=True, exist_ok=True)
        unpack_msg = f"Unpacking pipeline ZIP into: {target_dir}"
        logger.info(unpack_msg)
        self._send_update("RUNNING", unpack_msg, progress=50)

        unpacked_files: list[Path] = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for info in zf.infolist():
                    entry_name = info.filename
                    dest_path = self._safe_join(target_dir, entry_name)

                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    with zf.open(info, "r") as src, open(dest_path, "wb") as dst:
                        dst.write(src.read())

                    unpacked_files.append(dest_path)
                    rel = dest_path.relative_to(target_dir)
                    unpack_msg = f"Unpacked: {rel}"
                    logger.info(unpack_msg)
                    self._send_update("RUNNING", unpack_msg, progress=60)

        except zipfile.BadZipFile as e:
            msg = f"Invalid ZIP received from server: {e}"
            logger.error(msg)
            raise

        logger.info("All files written successfully.")

    @staticmethod
    def _read_env_value(env_path: Path, key: str) -> str | None:
        if not env_path.exists() or not env_path.is_file():
            return None
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() != key:
                    continue
                v = v.strip().strip('"').strip("'")
                return v or None
        except Exception:
            return None

        return None

    @staticmethod
    def _safe_join(base: Path, *parts: str) -> Path:
        candidate = (base.joinpath(*parts)).resolve()
        base_resolved = base.resolve()
        try:
            candidate.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Unsafe path detected (path traversal): {candidate}")

        return candidate
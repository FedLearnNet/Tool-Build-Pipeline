import logging
import subprocess
import sys
import traceback
import threading
from abc import ABC, abstractmethod
from typing import List, Tuple, Mapping

from src.client.client import ApiClient
from src.client.dto import StatusUpdateDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig

# Each step file will have its own logger
logger = logging.getLogger(__name__)


class BaseStep(ABC):
    """
    Abstract base class for all pipeline steps.
    Provides a common interface and shared functionality for running steps,
    handling errors, and reporting status to the API server.
    """

    def __init__(self, config: AppConfig, api_client: ApiClient, result: AppPublishInfoDTO):
        self.config: AppConfig = config
        self.api_client: ApiClient = api_client
        self.result: AppPublishInfoDTO = result
        self._log_buffer = []
        self._log_lock = threading.Lock()

    @property
    @abstractmethod
    def step_name(self) -> str:
        """The name of the step, e.g., 'CLONE_REPO'."""
        pass

    @property
    def allow_to_fail(self) -> bool:
        return False

    def run(self) -> bool:
        """
        Executes the step and handles reporting.
        This method acts as a template for all steps.
        """
        try:
            with self._log_lock:
                self._log_buffer = []

            logger.info(f"----- Starting Step: {self.step_name} -----")
            self._send_update("RUNNING", "Step started.", progress=0)

            self.execute()  # The core logic of the step is implemented here

            logger.info(f"----- Finished Step: {self.step_name} -----")
            self._send_update("SUCCESS", "Step completed successfully.", progress=100)
            return True
        except Exception as e:
            logger.error(f"----- Step Failed: {self.step_name} -----", exc_info=True)
            error_message = traceback.format_exc()

            if self.allow_to_fail:
                self._send_update(
                    status="WARNING",
                    logs=None,
                    progress=None,
                    error_code=e.__class__.__name__,
                    error_message=error_message
                )
            else:
                self._send_update(
                    status="FAILED",
                    logs=None,
                    progress=None,
                    error_code=e.__class__.__name__,
                    error_message=error_message
                )
            raise

    @abstractmethod
    def execute(self):
        """
        The main logic for the step. Must be implemented by subclasses.
        """
        pass

    def _send_update(
        self,
        status: str,
        logs: str = None,
        progress: int = None,
        error_code: str = None,
        error_message: str = None
    ):
        """Helper to send a status update to the server."""
        with self._log_lock:
            log_payload = logs if logs is not None else "".join(self._log_buffer)

            dto = StatusUpdateDTO(
                stepName=self.step_name,
                status=status,
                logs=log_payload,
                progress=progress,
                errorCode=error_code,
                errorMessage=error_message
            )
            self.api_client.send_status_update(dto)
            self._log_buffer = []

    def _append_log(self, line: str):
        with self._log_lock:
            self._log_buffer.append(line)

    def _flush_logs(self, progress: int = None):
        with self._log_lock:
            if not self._log_buffer:
                return
            logs = "".join(self._log_buffer)
            self._log_buffer = []

        self._send_update("RUNNING", logs=logs, progress=progress)

    @staticmethod
    def _try_extract_progress(line: str) -> int | None:
        """
        Parses lines like:
        'Step 3/10 ...'
        """
        if "Step" not in line or "/" not in line:
            return None

        try:
            parts = line.split("Step", 1)[1].strip().split(" ", 1)[0]
            current_str, total_str = parts.split("/", 1)
            current = int(current_str)
            total = int(total_str)
            if total <= 0:
                return None
            return int((current / total) * 100)
        except (ValueError, IndexError):
            return None

    def _stream_reader(
        self,
        pipe,
        output_list: List[str],
        is_stderr: bool = False
    ):
        """
        Reads one stream line-by-line and forwards output immediately.
        """
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break

                if is_stderr:
                    sys.stderr.write(line)
                    sys.stderr.flush()
                else:
                    sys.stdout.write(line)
                    sys.stdout.flush()

                output_list.append(line)
                self._append_log(line)

                if not is_stderr:
                    progress = self._try_extract_progress(line)
                    if progress is not None:
                        self._flush_logs(progress=progress)
                    else:
                        self._flush_logs()
                else:
                    self._flush_logs()
        finally:
            pipe.close()

    def _run_command(
        self,
        command: List[str],
        cwd: str = ".",
        env: Mapping[str, str] | None = None
    ) -> Tuple[int, str, str]:
        """
        Runs a shell command, streams stdout/stderr concurrently,
        and sends progress updates in real time.
        """
        logger.info(f"Executing command: {' '.join(command)}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,
            env=env
        )

        stdout_output: List[str] = []
        stderr_output: List[str] = []

        stdout_thread = threading.Thread(
            target=self._stream_reader,
            args=(process.stdout, stdout_output, False),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=self._stream_reader,
            args=(process.stderr, stderr_output, True),
            daemon=True
        )

        stdout_thread.start()
        stderr_thread.start()

        process.wait()
        stdout_thread.join()
        stderr_thread.join()

        self._flush_logs()

        return process.returncode, "".join(stdout_output), "".join(stderr_output)
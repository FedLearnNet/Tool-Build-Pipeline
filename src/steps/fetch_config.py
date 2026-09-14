import logging
from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class FetchConfigStep(BaseStep):
    """ Fetches the pipeline run configuration from the server. """

    @property
    def step_name(self) -> str:
        return "FETCH_CONFIG"

    def execute(self):
        """
        Fetches pipeline info from the API and populates the AppConfig object.
        """
        logger.info("Fetching pipeline run configuration from the server...")
        run_info = self.api_client.get_pipeline_info()

        # Update the main config object with the fetched data
        self.config.remote_info = run_info

        log_message = (
            f"Successfully fetched configuration:\n"
            f"  - Git Repo URL: {run_info.git_repo_url}\n"
            f"  - Image Name: {run_info.image_name}"
        )
        logger.info(log_message)
        # Add the final summary to the log buffer to be sent with the success status
        self._log_buffer.append(log_message)


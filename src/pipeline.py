import logging

from src.client.client import ApiClient
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig
from src.steps.build import BuildImageStep
from src.steps.clone import CloneRepoStep
from src.steps.collect_summary import CollectSummaryStep
from src.steps.fetch_config import FetchConfigStep
from src.steps.fetch_files import FetchFilesStep
from src.steps.malware import MalwareCheckStep
from src.steps.push import PushImageStep
from src.steps.scan import ScanImageStep
from src.steps.test import RunPytestStep

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config: AppConfig, client: ApiClient):
        self.config: AppConfig = config
        self.client: ApiClient = client
        self.result = AppPublishInfoDTO()
        self.steps = [
            FetchConfigStep(config, client, self.result),
            CloneRepoStep(config, client, self.result),
            FetchFilesStep(config, client, self.result),
            BuildImageStep(config, client, self.result),
            ScanImageStep(config, client, self.result),
            MalwareCheckStep(config, client, self.result),
            RunPytestStep(config, client, self.result),
            PushImageStep(config, client, self.result),
            CollectSummaryStep(config, client, self.result),
        ]

    def run(self):
        logger.info(f"--- Starting Pipeline Run: {self.config.pipeline_id} ---")
        for step in self.steps:
            logger.info(f"--- Executing Step: {step.__class__.__name__} ---")
            success = False
            try:
                success = step.run()
            except Exception as e:
                logger.error(f"Error during step {step.__class__.__name__}: {e}")
                if not step.allow_to_fail:
                    raise Exception(f"{step.__class__.__name__}: {e}")

            if step.allow_to_fail:
                continue
            if not success:
                logger.error(
                    f"--- Pipeline failed at step: {step.__class__.__name__}. Aborting. ---")
                return
        logger.info(f"--- Pipeline Run {self.config.pipeline_id} Completed Successfully ---")

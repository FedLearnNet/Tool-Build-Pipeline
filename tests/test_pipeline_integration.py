from src.config import load_config
from tests.mock.helper import get_api_recorder
from tests.mock.pipeline_test import TestPipeline

origin_url = "https://github.com/FedLearnNet/Tool-Train-test-split"


def test_pipeline_runs_through_all_steps_with_mocked_api():
    recorder = get_api_recorder(origin_url=origin_url)

    config = load_config()
    pipeline = TestPipeline(config, recorder)

    pipeline.run()

    recorder.check_updates()

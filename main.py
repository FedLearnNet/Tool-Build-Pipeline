import datetime
import logging
import sys
import uuid

from src.client.client import ApiClient
from src.config import load_config
from src.pipeline import Pipeline


def print_banner():
    """Prints a startup banner."""
    print("=" * 60)
    print("= Docker Build & Push Pipeline Client")
    print(f"= Started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


def setup_logging():
    """Configures the root logger for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout  # Log to standard output
    )


def main():
    """Main entry point for the pipeline client."""
    print_banner()
    setup_logging()

    logger = logging.getLogger(__name__)

    try:
        logger.info("Loading configuration from environment variables...")
        config = load_config()
        logger.info(f"Configuration loaded successfully")
        logger.info(f"Configuration: {config}")

        logger.info("Initializing API client...")
        api_client = ApiClient(config)
        logger.info("API client initialized.")

        logger.info("Starting pipeline execution...")
        pipeline = Pipeline(config, api_client)
        pipeline.run()
        logger.info("Pipeline execution finished successfully.")

    except Exception as e:
        logger.critical(f"A critical error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

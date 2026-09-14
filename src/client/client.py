import logging
from typing import List, Optional

import requests

from src.client.dto import StatusUpdateDTO, PipelineRunInfoDTO, FileDTO
from src.client.result_dto import AppPublishInfoDTO
from src.config import AppConfig

logger = logging.getLogger(__name__)


class ApiClient:
    """
    Handles all HTTP communication with the Quarkus backend API.
    """

    def __init__(self, config: AppConfig):
        self.config: AppConfig = config

    def get_base_url(self) -> str:
        return self.config.http_url.rstrip('/')

    def _headers(self) -> dict:
        """Build per-request headers (no persistent session)."""
        headers = {}
        if self.config.oauth_token:
            headers['Authorization'] = f'Bearer {self.config.oauth_token}'
        return headers

    def _request(self, method: str, url: str, **kwargs):
        req_headers = kwargs.pop('headers', {}) or {}
        merged_headers = {**self._headers(), **req_headers}

        try:
            response = requests.request(method, url, headers=merged_headers, **kwargs)

            # Treat any 2xx as success
            if response.ok:
                return response

            # Provide useful diagnostics for non-2xx responses
            body_preview = (response.text or "").strip()
            if len(body_preview) > 2000:
                body_preview = body_preview[:2000] + "...<truncated>"

            logger.error(
                f"{method} {url} -> {response.status_code} {response.reason}; "
                f"response body (preview): {body_preview}"
            )

            raise RuntimeError(
                f"Failed to {method} {url} (HTTP {response.status_code} {response.reason}). "
                f"Response body (preview): {body_preview}"
            )

        except requests.exceptions.RequestException as e:
            # Network/DNS/timeout/connection errors etc.
            logger.error(f"Request error on {method} {url}: {e}")
            raise RuntimeError(f"Failed to {method} {url} due to request error: {e}") from e

    def send_status_update(self, update_dto: StatusUpdateDTO):
        """
        Sends a pipeline step status update to the server.
        """
        url = f"{self.get_base_url()}/pipeline/{self.config.pipeline_id}/update"
        params = {'secret': self.config.pipeline_secret}
        payload = update_dto.model_dump(by_alias=True, exclude_none=True)
        try:
            response = self._request('PUT', url, json=payload, params=params, timeout=30)
            response.raise_for_status()
            logger.info(
                f"Successfully sent status update for step: {update_dto.step_name} -> {update_dto.status}")
        except Exception as e:
            logger.error(f"Error sending status update: {e}")

    def get_pipeline_info(self) -> PipelineRunInfoDTO:
        """ Fetches the pipeline run info from the server. """
        url = f"{self.get_base_url()}/pipeline/{self.config.pipeline_id}/info"
        params = {'secret': self.config.pipeline_secret}
        logger.info(f"Fetching pipeline info from {url}")
        response = self._request('GET', url, params=params, timeout=30)
        response.raise_for_status()
        return PipelineRunInfoDTO(**response.json())

    def get_zip_for_pipeline(self) -> Optional[bytes]:
        """
        Fetches a single ZIP (application/zip) containing all pipeline files.

        Returns:
          - ZIP bytes if found (HTTP 200)
          - None if not found (HTTP 404)

        Raises:
          - RuntimeError for any non-404 non-2xx response with safe body preview
          - RuntimeError for request/timeout/network errors
        """
        url = f"{self.get_base_url()}/pipeline/{self.config.pipeline_id}/zip"
        params = {"secret": self.config.pipeline_secret}
        headers = self._headers()

        logger.info("Fetching pipeline ZIP from %s", url)

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=60)
        except requests.exceptions.RequestException as e:
            logger.error("Request error on GET %s: %s", url, e)
            raise RuntimeError(f"Failed to GET {url} due to request error: {e}") from e

        if resp.status_code == 404:
            logger.info("Pipeline ZIP not found (404) for pipeline_id=%s", self.config.pipeline_id)
            return None

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "application/zip" not in content_type:
            logger.warning("Expected application/zip but got Content-Type=%r", content_type)

        return resp.content

    def upload_summary(self, result: AppPublishInfoDTO):
        """Uploads the final app publish info to the server."""
        url = f"{self.get_base_url()}/pipeline/{self.config.pipeline_id}/summary"
        params = {'secret': self.config.pipeline_secret}
        payload = result.model_dump(by_alias=True, exclude_none=True)
        try:
            logger.info(f"Uploading summary: {payload}")
            response = self._request('PUT', url, json=payload, params=params, timeout=30)
            if not response.ok:
                body_preview = (response.text or "").strip()

                logger.error(
                    f"PUT {url} -> {response.status_code} {response.reason}; "
                    f"response body (preview): {body_preview}"
                )
            response.raise_for_status()
            logger.info(
                f"Successfully uploaded publish info for pipeline: {self.config.pipeline_id}")
        except Exception as e:
            logger.error(
                f"Error uploading publish info to {url} for pipeline {self.config.pipeline_id}: {e}")
            raise

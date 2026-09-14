import logging
import uuid

from src.steps.base import BaseStep

logger = logging.getLogger(__name__)


class PushImageStep(BaseStep):
    def __init__(self, config, api_client, result):
        super().__init__(config, api_client, result)
        unique_suffix = uuid.uuid4().hex[:12]
        self.context_name = f"fedDB-context-{unique_suffix}"
        self.builder_name = f"fedDBBuilder-{unique_suffix}"

    @property
    def step_name(self) -> str:
        return "PUSH_IMAGE"

    def _cosign_available(self) -> bool:
        try:
            return_code, _, _ = self._run_command(["cosign", "version"])
            return return_code == 0
        except FileNotFoundError:
            return False

    def _buildx_available(self) -> bool:
        try:
            return_code, _, _ = self._run_command(["docker", "buildx", "version"])
            return return_code == 0
        except FileNotFoundError:
            return False

    def _get_platform_arg(self) -> str:
        platforms = []
        for platform in self.config.buildx_platforms:
            if platform not in platforms:
                platforms.append(platform)
        return ",".join(platforms)

    def _build_buildx_command(self, builder_name: str, image_name: str) -> list[str]:
        command = [
            "docker", "buildx", "build",
            "--builder", builder_name,
            "--platform", self._get_platform_arg(),
            "--push",
            "--progress", "plain",
            "-t", image_name,
        ]

        if self.config.buildx_sbom:
            command.append("--sbom=true")

        if self.config.buildx_provenance_mode:
            command.append(f"--provenance=mode={self.config.buildx_provenance_mode}")

        command.append(self.config.repo_path)
        return command

    def _sign_image(self, image_name: str) -> None:
        if not self.config.cosign_sign:
            return

        if not self._cosign_available():
            raise Exception("Cosign signing is enabled but cosign is not available in this environment.")

        self._send_update(
            "RUNNING",
            logs=f"Signing pushed image with cosign: {image_name}"
        )
        logger.info("Signing pushed image with cosign: %s", image_name)
        return_code, _, stderr = self._run_command(["cosign", "sign", "--yes", image_name])
        if return_code != 0:
            raise Exception(f"Cosign signing failed. Error: {stderr}")

        logger.info("Image signed successfully with cosign.")

    def prepare_buildx(self) -> str:
        """
        Mirrors our standart gitlab ci/cd stuff:
          - docker context create <unique-context>
          - docker buildx create --name <unique-builder> --use <unique-context>
          - docker buildx inspect --bootstrap

        Returns the builder name.
        """
        if not self._buildx_available():
            raise Exception("Docker buildx is not available in this environment.")

        logger.info("Preparing Docker buildx builder (context + builder).")

        context_name = self.context_name
        builder_name = self.builder_name

        def _context_exists(name: str) -> bool:
            rc, _, _ = self._run_command(["docker", "context", "inspect", name])
            return rc == 0

        def _builder_exists(name: str) -> bool:
            rc, _, _ = self._run_command(["docker", "buildx", "inspect", name])
            return rc == 0

        def _create_context_if_needed() -> None:
            if _context_exists(context_name):
                logger.info(f"Using existing docker context: {context_name}")
                return

            logger.info(f"Creating docker context: {context_name}")
            rc, _, stderr = self._run_command(["docker", "context", "create", context_name])
            if rc != 0:
                lower = (stderr or "").lower()
                if "already exists" in lower or "exists" in lower:
                    logger.warning(f"Docker context '{context_name}' already exists. Continuing.")
                    return
                raise Exception(
                    f"Failed to create docker context '{context_name}'. Error: {stderr}"
                )

        def _create_builder_if_needed() -> None:
            if _builder_exists(builder_name):
                logger.info(f"Using existing buildx builder: {builder_name}")
                return

            logger.info(f"Creating buildx builder: {builder_name} (using context: {context_name})")
            create_cmd = [
                "docker", "buildx", "create",
                "--name", builder_name,
                "--use",
                context_name,
            ]
            rc, _, stderr = self._run_command(create_cmd)
            if rc != 0:
                lower = (stderr or "").lower()
                if "already exists" in lower or "exists" in lower:
                    logger.warning(
                        f"Buildx builder '{builder_name}' already exists according to stderr. Continuing."
                    )
                    return
                raise Exception(
                    f"Failed to create buildx builder '{builder_name}'. Error: {stderr}"
                )

        def _inspect_bootstrap() -> None:
            rc, _, stderr = self._run_command(
                ["docker", "buildx", "inspect", "--builder", builder_name, "--bootstrap"]
            )
            if rc != 0:
                raise Exception(
                    f"Failed to bootstrap buildx builder '{builder_name}'. Error: {stderr}"
                )

        _create_context_if_needed()
        _create_builder_if_needed()
        _inspect_bootstrap()

        logger.info(f"Buildx builder ready: {builder_name} (context: {context_name})")
        return builder_name

    def remove_buildx(self) -> None:
        """
        Removes the buildx builder + docker context created by prepare_buildx().
        Safe to call even if they do not exist.
        """
        context_name = self.context_name
        builder_name = self.builder_name

        logger.info("Removing Docker buildx builder + context.")

        rc, _, stderr = self._run_command(["docker", "buildx", "rm", "-f", builder_name])
        if rc == 0:
            logger.info(f"Removed buildx builder: {builder_name}")
        else:
            lower = (stderr or "").lower()
            if "no such" in lower or "not found" in lower or "does not exist" in lower:
                logger.info(f"Buildx builder not present: {builder_name}")
            else:
                logger.warning(f"Failed to remove buildx builder '{builder_name}'. Error: {stderr}")

        rc, _, stderr = self._run_command(["docker", "context", "rm", "-f", context_name])
        if rc == 0:
            logger.info(f"Removed docker context: {context_name}")
        else:
            lower = (stderr or "").lower()
            if "no such" in lower or "not found" in lower or "does not exist" in lower:
                logger.info(f"Docker context not present: {context_name}")
            else:
                logger.warning(f"Failed to remove docker context '{context_name}'. Error: {stderr}")

    def execute(self):
        image_name = self.config.get_docker_name()

        logger.info(f"Pushing image: {image_name} to registry.")
        use_buildx = self.config.use_buildx
        buildx_available = self._buildx_available()

        if use_buildx and not buildx_available:
            logger.warning("Buildx is enabled in config but not available. Falling back to normal push.")
            self._send_update("RUNNING", logs="Buildx enabled but not available. Falling back to normal push.")
            use_buildx = False

        if use_buildx:
            platform_arg = self._get_platform_arg()
            builder_name = self.prepare_buildx()
            logger.info(f"Using buildx platform: {platform_arg}")
            self._send_update(
                "RUNNING",
                logs=(
                    f"Building Docker image with buildx for platforms: {platform_arg}. "
                    f"SBOM={'enabled' if self.config.buildx_sbom else 'disabled'}, "
                    f"provenance mode={self.config.buildx_provenance_mode or 'disabled'}."
                )
            )
            command = self._build_buildx_command(builder_name, image_name)
        else:
            self._send_update(
                "RUNNING",
                logs="Pushing prebuilt Docker image without buildx attestations."
            )
            command = ["docker", "push", image_name]

        try:
            return_code, _, stderr = self._run_command(command)
        finally:
            if use_buildx:
                self.remove_buildx()

        if return_code != 0:
            raise Exception(f"Docker push failed. Error: {stderr}")

        self._sign_image(image_name)
        logger.info("Image pushed successfully.")

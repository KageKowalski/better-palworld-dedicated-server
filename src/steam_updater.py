"""SteamCMD updater that invokes SteamCMD to update the Palworld Dedicated Server.

Encapsulates subprocess management, path validation, and timeout enforcement
for the SteamCMD update process during maintenance cycles.
"""

import asyncio
import logging
from pathlib import Path

from src.models import UpdateResult

logger = logging.getLogger(__name__)


class SteamUpdater:
    """Invokes SteamCMD to update the Palworld Dedicated Server installation.

    Validates that the configured paths exist before attempting an update.
    Returns an UpdateResult dataclass indicating success, skip, or failure
    rather than raising exceptions.
    """

    def __init__(
        self,
        steamcmd_path: str,
        install_dir: str,
        app_id: int = 2394010,
        timeout_seconds: int = 300,
    ) -> None:
        """Initialize the SteamUpdater.

        Args:
            steamcmd_path: Path to the SteamCMD executable.
            install_dir: Path to the Palworld Dedicated Server installation directory.
            app_id: Steam app ID to update (default: 2394010 for Palworld Dedicated Server).
            timeout_seconds: Maximum seconds to wait for SteamCMD to complete before terminating.
        """
        self._steamcmd_path = steamcmd_path
        self._install_dir = install_dir
        self._app_id = app_id
        self._timeout_seconds = timeout_seconds

    async def update(self) -> UpdateResult:
        """Run SteamCMD to update the server installation.

        Validates paths exist before invoking the subprocess. Enforces a timeout
        and terminates the process if it exceeds the configured duration.

        Returns:
            UpdateResult indicating the outcome of the update attempt.
        """
        # Validate steamcmd_path
        if not self._steamcmd_path:
            logger.warning("steamcmd_path is empty, skipping update")
            return UpdateResult(success=False, skipped=True)

        steamcmd = Path(self._steamcmd_path)
        if not steamcmd.exists():
            logger.warning(
                "SteamCMD executable not found at '%s', skipping update",
                self._steamcmd_path,
            )
            return UpdateResult(success=False, skipped=True)

        # Validate install_dir
        if not self._install_dir:
            logger.warning("steam_app_install_dir is empty, skipping update")
            return UpdateResult(success=False, skipped=True)

        install_dir = Path(self._install_dir)
        if not install_dir.exists():
            logger.warning(
                "Install directory not found at '%s', skipping update",
                self._install_dir,
            )
            return UpdateResult(success=False, skipped=True)

        # Build SteamCMD arguments
        args = [
            str(steamcmd),
            "+force_install_dir",
            str(install_dir),
            "+login",
            "anonymous",
            "+app_update",
            str(self._app_id),
            "validate",
            "+quit",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                await asyncio.wait_for(process.wait(), timeout=self._timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(
                    "SteamCMD timed out after %d seconds, terminating process",
                    self._timeout_seconds,
                )
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    process.kill()
                return UpdateResult(
                    success=False,
                    timed_out=True,
                    error_message=f"SteamCMD timed out after {self._timeout_seconds} seconds",
                )

            if process.returncode == 0:
                logger.info("SteamCMD update completed successfully")
                return UpdateResult(success=True)
            else:
                error_msg = f"SteamCMD exited with code {process.returncode}"
                logger.warning(error_msg)
                return UpdateResult(success=False, error_message=error_msg)

        except OSError as e:
            error_msg = f"Failed to execute SteamCMD: {e}"
            logger.warning(error_msg)
            return UpdateResult(success=False, error_message=error_msg)

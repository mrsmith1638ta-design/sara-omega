import logging

logger = logging.getLogger("sara-nexus-cipmu.main_patched")

try:
    from main import app  # type: ignore
    logger.info("Loaded base app from main:app")
except Exception as exc:
    raise RuntimeError("sara-nexus-cipmu base main:app is required") from exc

from cipmu_patch import register_cipmu

register_cipmu(app)

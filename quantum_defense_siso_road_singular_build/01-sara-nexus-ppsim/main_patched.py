import logging

logger = logging.getLogger("sara-nexus-ppsim.main_patched")

try:
    from main import app  # type: ignore
    logger.info("Loaded base app from main:app")
except Exception as exc:
    raise RuntimeError("sara-nexus-ppsim base main:app is required") from exc

from pqc_patch import register_pqc
register_pqc(app)

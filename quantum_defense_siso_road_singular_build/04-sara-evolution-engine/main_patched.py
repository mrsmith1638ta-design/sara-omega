import logging

logger = logging.getLogger("sara-evolution-engine.main_patched")

try:
    from main import app  # type: ignore
    logger.info("Loaded base app from main:app")
except Exception as exc:
    raise RuntimeError("sara-evolution-engine base main:app is required") from exc

from quantum_patch import register_quantum_fabric

register_quantum_fabric(app)

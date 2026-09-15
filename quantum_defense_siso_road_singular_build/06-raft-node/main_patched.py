import logging

logger = logging.getLogger("raft-node.main_patched")

try:
    from main import app  # type: ignore
    logger.info("Loaded base app from main:app")
except Exception as exc:
    raise RuntimeError("raft-node base main:app is required") from exc

from raft_pqc_patch import register_raft_pqc

register_raft_pqc(app)

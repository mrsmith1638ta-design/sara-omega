from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite+pysqlite:///:memory:"
    road_mandatory: bool = False
    sios_mandatory: bool = False
    max_request_bytes: int = 1_000_000

    @classmethod
    def from_env(cls):
        size = int(os.getenv("SARA_MAX_REQUEST_BYTES", "1000000"))
        if size <= 0:
            raise ValueError("SARA_MAX_REQUEST_BYTES must be positive")
        return cls(
            database_url=os.getenv("SARA_DATABASE_URL", cls.database_url),
            road_mandatory=os.getenv("SARA_ROAD_MANDATORY", "false").lower() == "true",
            sios_mandatory=os.getenv("SARA_SIOS_MANDATORY", "false").lower() == "true",
            max_request_bytes=size,
        )

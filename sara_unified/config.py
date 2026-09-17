from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite+pysqlite:///:memory:"
    road_mandatory: bool = False
    sios_mandatory: bool = False
    max_request_bytes: int = 1_000_000
    voice_enabled: bool = False
    piper_service_url: str = "http://127.0.0.1:5000"
    piper_service_token: str = ""
    voice_timeout_seconds: float = 15.0
    voice_max_characters: int = 4000
    voice_1_1_enabled: bool = False
    voice_accessibility_public_enabled: bool = False

    @classmethod
    def from_env(cls):
        size = int(os.getenv("SARA_MAX_REQUEST_BYTES", "1000000"))
        timeout = float(os.getenv("SARA_VOICE_TIMEOUT_SECONDS", "15.0"))
        max_characters = int(os.getenv("SARA_VOICE_MAX_CHARACTERS", "4000"))
        if size <= 0:
            raise ValueError("SARA_MAX_REQUEST_BYTES must be positive")
        if timeout <= 0:
            raise ValueError("SARA_VOICE_TIMEOUT_SECONDS must be positive")
        if max_characters <= 0:
            raise ValueError("SARA_VOICE_MAX_CHARACTERS must be positive")
        return cls(
            database_url=os.getenv("SARA_DATABASE_URL", cls.database_url),
            road_mandatory=os.getenv("SARA_ROAD_MANDATORY", "false").lower() == "true",
            sios_mandatory=os.getenv("SARA_SIOS_MANDATORY", "false").lower() == "true",
            max_request_bytes=size,
            voice_enabled=os.getenv("SARA_VOICE_ENABLED", "false").lower() == "true",
            piper_service_url=os.getenv("SARA_PIPER_SERVICE_URL", cls.piper_service_url),
            piper_service_token=os.getenv("SARA_PIPER_SERVICE_TOKEN", ""),
            voice_timeout_seconds=timeout,
            voice_max_characters=max_characters,
            voice_1_1_enabled=os.getenv("SARA_VOICE_1_1_ENABLED", "false").lower() == "true",
            voice_accessibility_public_enabled=(
                os.getenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", "false").lower() == "true"
            ),
        )

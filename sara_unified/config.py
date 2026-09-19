from dataclasses import dataclass
import os


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite+pysqlite:///:memory:"
    road_mandatory: bool = False
    sios_mandatory: bool = False
    max_request_bytes: int = 1_000_000
    governance_enforcement_required: bool = False
    governance_signing_key: str = ""
    governance_tenant_id: str = "default"
    voice_enabled: bool = False
    piper_service_url: str = "http://127.0.0.1:5000"
    piper_service_token: str = ""
    voice_timeout_seconds: float = 15.0
    voice_max_characters: int = 4000
    voice_1_1_enabled: bool = False
    voice_accessibility_public_enabled: bool = False
    voice_1_1a_enabled: bool = False
    voice_1_1a_user_jobs_per_minute: int = 6
    voice_1_1a_user_jobs_per_day: int = 100
    voice_1_1a_user_characters_per_day: int = 100_000
    voice_1_1a_tenant_jobs_per_minute: int = 20
    voice_1_1a_tenant_jobs_per_day: int = 500
    voice_1_1a_tenant_characters_per_day: int = 500_000
    voice_1_1a_user_concurrency: int = 1
    voice_1_1a_tenant_concurrency: int = 4
    voice_1_1a_lease_seconds: int = 60

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
            governance_enforcement_required=(
                os.getenv("SARA_GOVERNANCE_ENFORCEMENT_REQUIRED", "true").lower() == "true"
            ),
            governance_signing_key=os.getenv("SARA_GOVERNANCE_SIGNING_KEY", ""),
            governance_tenant_id=os.getenv("SARA_GOVERNANCE_TENANT_ID", "default"),
            voice_enabled=os.getenv("SARA_VOICE_ENABLED", "false").lower() == "true",
            piper_service_url=os.getenv("SARA_PIPER_SERVICE_URL", cls.piper_service_url),
            piper_service_token=os.getenv("SARA_PIPER_SERVICE_TOKEN", ""),
            voice_timeout_seconds=timeout,
            voice_max_characters=max_characters,
            voice_1_1_enabled=os.getenv("SARA_VOICE_1_1_ENABLED", "false").lower() == "true",
            voice_accessibility_public_enabled=(
                os.getenv("SARA_VOICE_ACCESSIBILITY_PUBLIC_ENABLED", "false").lower() == "true"
            ),
            voice_1_1a_enabled=os.getenv("SARA_VOICE_1_1A_ENABLED", "false").lower() == "true",
            voice_1_1a_user_jobs_per_minute=_positive_int_env(
                "SARA_VOICE_1_1A_USER_JOBS_PER_MINUTE", 6
            ),
            voice_1_1a_user_jobs_per_day=_positive_int_env(
                "SARA_VOICE_1_1A_USER_JOBS_PER_DAY", 100
            ),
            voice_1_1a_user_characters_per_day=_positive_int_env(
                "SARA_VOICE_1_1A_USER_CHARACTERS_PER_DAY", 100_000
            ),
            voice_1_1a_tenant_jobs_per_minute=_positive_int_env(
                "SARA_VOICE_1_1A_TENANT_JOBS_PER_MINUTE", 20
            ),
            voice_1_1a_tenant_jobs_per_day=_positive_int_env(
                "SARA_VOICE_1_1A_TENANT_JOBS_PER_DAY", 500
            ),
            voice_1_1a_tenant_characters_per_day=_positive_int_env(
                "SARA_VOICE_1_1A_TENANT_CHARACTERS_PER_DAY", 500_000
            ),
            voice_1_1a_user_concurrency=_positive_int_env(
                "SARA_VOICE_1_1A_USER_CONCURRENCY", 1
            ),
            voice_1_1a_tenant_concurrency=_positive_int_env(
                "SARA_VOICE_1_1A_TENANT_CONCURRENCY", 4
            ),
            voice_1_1a_lease_seconds=_positive_int_env(
                "SARA_VOICE_1_1A_LEASE_SECONDS", 60
            ),
        )

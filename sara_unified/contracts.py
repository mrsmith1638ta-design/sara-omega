from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

class OperationClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    STATE_CHANGING = "STATE_CHANGING"
    SENSITIVE = "SENSITIVE"
    DESTRUCTIVE = "DESTRUCTIVE"

@dataclass(frozen=True)
class RequestContext:
    actor_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    reason: str
    authority: str
    evidence: dict[str, Any] = field(default_factory=dict)

"""Data classes for the delegator system."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class DelegationRequest:
    task: str
    model: str
    workflow: str = "subagent-driven"
    from_agent: str = ""
    task_type: str = ""
    from_file: Optional[str] = None
    output: Optional[str] = None
    stream: bool = False
    no_worktree: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class DelegationResult:
    success: bool
    provider_used: str
    model_used: str
    fallback_count: int
    error: Optional[str] = None
    output: Optional[str] = None
    duration_ms: int = 0
    request_id: str = ""


@dataclass
class CooldownEntry:
    failure_count: int = 0
    last_failure: Optional[str] = None
    cooldown_until: Optional[str] = None

    def is_active(self) -> bool:
        if not self.cooldown_until:
            return False
        try:
            until = datetime.fromisoformat(self.cooldown_until)
            return datetime.now(timezone.utc) < until
        except (ValueError, TypeError):
            return False

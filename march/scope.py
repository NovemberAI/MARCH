"""Server-owned request scope. Only trusted server code constructs it."""

from dataclasses import dataclass

from march.config import FIXTURE_EMPLOYEES


class ScopeError(PermissionError):
    """Raised for any scope violation; messages never reveal other employees' data."""


@dataclass(frozen=True)
class RequestScope:
    mode: str
    org_id: str
    employee_id: str
    session_id: str
    identity_source: str  # "manual_fixture" | "voice_match"

    def __post_init__(self) -> None:
        if self.mode not in {"demo", "eval"}:
            raise ScopeError("unsupported mode")
        if self.employee_id not in FIXTURE_EMPLOYEES:
            raise ScopeError("unknown employee")
        if self.identity_source not in {"manual_fixture", "voice_match"}:
            raise ScopeError("unsupported identity source")

    def filter(self) -> dict[str, str]:
        return {"mode": self.mode, "orgId": self.org_id, "employeeId": self.employee_id}

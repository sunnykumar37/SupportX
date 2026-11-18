from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TicketState:
    ticket_id: str
    customer_id: str
    original_message: str
    detected_category: str = ""
    confidence_score: float = 0.0
    classification_explanation: str = ""
    assigned_specialist: str = ""
    retrieved_knowledge: list[dict[str, Any]] = field(default_factory=list)
    previous_context: list[dict[str, Any]] = field(default_factory=list)
    specialist_result: str = ""
    draft_response: str = ""
    reviewer_status: str = "pending"
    reviewer_feedback: str = ""
    revision_attempts: int = 0
    escalation_status: str = "not_required"
    escalation_reason: str = ""
    final_response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    execution_trace: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def new(cls, customer_id: str, message: str) -> "TicketState":
        return cls(ticket_id=f"T-{uuid.uuid4().hex[:10].upper()}", customer_id=customer_id, original_message=message)

    def update(self, **values: Any) -> None:
        for key, value in values.items():
            if not hasattr(self, key):
                raise AttributeError(f"Unknown ticket field: {key}")
            setattr(self, key, value)
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def state_from_dict(data: dict[str, Any]) -> TicketState:
    return TicketState(**data)
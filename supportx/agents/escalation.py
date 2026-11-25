
import json
from pathlib import Path

from ..config import settings
from ..logging_utils import ExecutionLogger
from ..models import TicketState


class EscalationRouter:
    def __init__(self, logger: ExecutionLogger, storage_dir: Path):
        self.logger = logger
        self.records: list[dict] = []
        self.records_path = storage_dir / "escalations.jsonl"
        self.records_path.parent.mkdir(parents=True, exist_ok=True)

    def check_escalation_threshold(
        self, ticket: TicketState
    ) -> tuple[bool, str]:

        # Respect an explicit escalation request from a specialist.
        if ticket.escalation_reason:
            return True, ticket.escalation_reason

        if ticket.confidence_score < settings.confidence_threshold:
            return True, (
                "Classification confidence is below the support threshold."
            )

        if "not enough relevant" in (
            ticket.specialist_result or ""
        ).lower():
            return True, (
                "The specialist could not find sufficient verified information."
            )

        if ticket.reviewer_status != "approved":
            return True, (
                "The response was not approved by the reviewer "
                "within the revision limit."
            )

        return False, ""

    def create_escalation_record(
        self, ticket: TicketState, reason: str
    ) -> dict:

        record = {
            "ticket_id": ticket.ticket_id,
            "customer_id": ticket.customer_id,
            "category": ticket.detected_category,
            "confidence": ticket.confidence_score,
            "specialist": ticket.assigned_specialist,
            "reason": reason,
            "summary": ticket.original_message
        }

        self.records.append(record)

        with self.records_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record) + "\n")

        return record

    def run(self, ticket: TicketState) -> TicketState:

        self.logger.event(
            "agent_activated",
            ticket,
            agent="escalation_router"
        )

        should_escalate, reason = self.check_escalation_threshold(ticket)

        ticket.tool_calls.append("check_escalation_threshold")

        if should_escalate:
            ticket.escalation_status = "escalated"
            ticket.escalation_reason = reason

            self.create_escalation_record(ticket, reason)
            ticket.tool_calls.append("create_escalation_record")

        else:
            ticket.escalation_status = "not_required"

        self.logger.event(
            "escalation_decision",
            ticket,
            status=ticket.escalation_status,
            reason=reason
        )

        return ticket

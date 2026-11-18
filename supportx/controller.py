from pathlib import Path

from .agents.account import AccountSpecialist
from .agents.billing import BillingSpecialist
from .agents.classifier import ClassifierAgent
from .agents.escalation import EscalationRouter
from .agents.reviewer import ReviewerAgent
from .agents.technical import TechnicalSpecialist
from .config import DATA_DIR, STORAGE_DIR, settings
from .logging_utils import ExecutionLogger
from .memory import ConversationMemory
from .models import TicketState
from .rag import KnowledgeBase
from .storage import TicketRepository


class SupportXController:
    def __init__(self, storage_dir: Path = STORAGE_DIR):
        storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = ExecutionLogger(storage_dir / "execution.jsonl")
        self.repository = TicketRepository(storage_dir / "tickets.json")
        self.memory = ConversationMemory(self.repository)
        self.classifier = ClassifierAgent(self.logger)
        self.billing = BillingSpecialist(self.logger, DATA_DIR / "billing_records.json")
        self.technical = TechnicalSpecialist(self.logger, KnowledgeBase())
        self.account = AccountSpecialist(self.logger, DATA_DIR / "accounts.json")
        self.reviewer = ReviewerAgent(self.logger)
        self.escalation = EscalationRouter(self.logger, storage_dir)

    def _revise_response(self, ticket: TicketState) -> None:
        ticket.revision_attempts += 1
        ticket.draft_response = f"{ticket.draft_response.rstrip('.')} Please follow the verified next step above, and contact human support if it does not resolve the issue."

    def process(self, customer_id: str, message: str) -> TicketState:
        if not customer_id.strip() or not message.strip():
            raise ValueError("Customer ID and message are required.")
        ticket = TicketState.new(customer_id.strip(), message.strip())
        self.logger.event("ticket_received", ticket)
        ticket.previous_context = self.memory.retrieve(ticket.customer_id)
        self.classifier.run(ticket)
        if ticket.detected_category == "Billing":
            self.billing.run(ticket)
        elif ticket.detected_category == "Technical":
            self.technical.run(ticket)
        elif ticket.detected_category == "Account":
            self.account.run(ticket)
        else:
            ticket.specialist_result = "The request could not be assigned to a specialist."
            ticket.draft_response = "I need a little more detail to route this request to the right support specialist."
        while ticket.revision_attempts < settings.max_revision_attempts:
            self.reviewer.review(ticket)
            if ticket.reviewer_status == "approved":
                break
            self._revise_response(ticket)
        self.escalation.run(ticket)
        if ticket.reviewer_status == "approved" and ticket.escalation_status == "not_required":
            ticket.final_response = ticket.draft_response
        else:
            ticket.final_response = ticket.draft_response if ticket.reviewer_status == "approved" else "Your request has been sent to human support for review."
        self.logger.event("final_response", ticket, response=ticket.final_response)
        self.memory.remember(ticket)
        return ticket

    def dashboard(self) -> dict:
        tickets = self.repository.all()
        return {
            "total": len(tickets),
            "billing": sum(t.detected_category == "Billing" for t in tickets),
            "technical": sum(t.detected_category == "Technical" for t in tickets),
            "account": sum(t.detected_category == "Account" for t in tickets),
            "resolved": sum(t.escalation_status == "not_required" and bool(t.final_response) for t in tickets),
            "escalated": sum(t.escalation_status == "escalated" for t in tickets),
            "recent": [ticket.to_dict() for ticket in tickets[-10:]],
        }
from pathlib import Path

from supportx.agents.reviewer import ReviewerAgent
from supportx.controller import SupportXController
from supportx.logging_utils import ExecutionLogger
from supportx.models import TicketState


def controller(tmp_path: Path) -> SupportXController:
    return SupportXController(tmp_path)


def test_billing_ticket(tmp_path):
    ticket = controller(tmp_path).process("CUST-001", "I was charged twice for my subscription")
    assert ticket.detected_category == "Billing"
    assert ticket.assigned_specialist == "billing_specialist"
    assert {"lookup_invoice", "check_refund_policy"}.issubset(ticket.tool_calls)
    assert ticket.escalation_status == "not_required"


def test_technical_ticket_uses_rag(tmp_path):
    ticket = controller(tmp_path).process("CUST-001", "The application shows a blank screen error")
    assert ticket.detected_category == "Technical"
    assert ticket.retrieved_knowledge
    assert "retrieve_knowledge" in ticket.tool_calls


def test_account_ticket(tmp_path):
    ticket = controller(tmp_path).process("CUST-002", "I cannot log in to my account")
    assert ticket.detected_category == "Account"
    assert "check_account_status" in ticket.tool_calls
    assert "password" not in ticket.final_response.lower() or "password reset" in ticket.final_response.lower()


def test_low_confidence_ticket_escalates(tmp_path):
    ticket = controller(tmp_path).process("CUST-001", "It does not work")
    assert ticket.detected_category == "Other"
    assert ticket.escalation_status == "escalated"


def test_unresolved_technical_ticket_escalates(tmp_path):
    ticket = controller(tmp_path).process("CUST-001", "The quantum telemetry daemon has a zorp failure")
    assert ticket.detected_category == "Technical"
    assert ticket.escalation_status == "escalated"
    assert "not enough" in ticket.specialist_result.lower()


def test_follow_up_retrieves_customer_memory(tmp_path):
    app = controller(tmp_path)
    first = app.process("CUST-003", "How do I request a refund?")
    second = app.process("CUST-003", "What was the status of my earlier request?")
    assert second.previous_context
    assert second.previous_context[0]["ticket_id"] == first.ticket_id


def test_reviewer_rejects_incomplete_response(tmp_path):
    logger = ExecutionLogger(tmp_path / "review.jsonl")
    ticket = TicketState.new("CUST-001", "help")
    ticket.update(detected_category="Other", draft_response="bad")
    reviewed = ReviewerAgent(logger).review(ticket)
    assert reviewed.reviewer_status == "revision_required"
    assert "check_reply_tone" in reviewed.tool_calls
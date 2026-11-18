
import json
from pathlib import Path

from ..logging_utils import ExecutionLogger
from ..models import TicketState


class BillingSpecialist:
    def __init__(self, logger: ExecutionLogger, records_path: Path):
        self.logger = logger
        self.records_path = records_path

    def lookup_invoice(
        self, customer_id: str, invoice_id: str | None = None
    ) -> list[dict]:
        records = json.loads(
            self.records_path.read_text(encoding="utf-8")
        )

        invoices = [
            record
            for record in records
            if record.get("customer_id") == customer_id
        ]

        if invoice_id:
            invoices = [
                record for record in invoices
                if record.get("invoice_id", "").lower()
                == invoice_id.lower()
            ]

        return invoices

    def check_refund_policy(
        self, message: str, invoices: list[dict]
    ) -> str:
        if not any(
            term in message.lower()
            for term in ("refund", "money back", "charged twice", "duplicate")
        ):
            return "Please contact support if you need a refund or payment review."

        if not invoices:
            return "No matching invoice was found, so refund eligibility cannot be verified."

        if all(invoice.get("status", "").lower() == "refunded"
               for invoice in invoices):
            return "The matching invoice is already marked as refunded."

        return (
            "A refund request has been identified. "
            "The invoice details are available for review, "
            "but refund eligibility requires verification against the official policy."
        )

    def run(self, ticket: TicketState) -> TicketState:
        self.logger.event(
            "agent_activated", ticket, agent="billing_specialist"
        )

        # Extract an invoice ID if the customer supplied one.
        import re
        match = re.search(
            r"\bINV-\d+\b", ticket.original_message, re.IGNORECASE
        )
        invoice_id = match.group(0) if match else None

        invoices = self.lookup_invoice(ticket.customer_id, invoice_id)

        if invoices:
            invoice_details = "; ".join(
                f"Invoice {invoice['invoice_id']}: "
                f"${invoice['amount']:.2f}, "
                f"status {invoice['status']}, "
                f"date {invoice['date']}"
                for invoice in invoices
            )
            ticket.specialist_result = (
                f"Found {len(invoices)} matching invoice record(s). "
                f"{invoice_details}"
            )
        else:
            ticket.specialist_result = (
                "No matching invoice record was found for this customer."
            )

        policy = self.check_refund_policy(
            ticket.original_message, invoices
        )

        ticket.draft_response = (
            f"I reviewed your billing request. "
            f"{ticket.specialist_result} {policy}"
        )

        ticket.tool_calls.extend([
            "lookup_invoice",
            "check_refund_policy"
        ])

        self.logger.event(
            "specialist_response", ticket, specialist="billing"
        )

        return ticket

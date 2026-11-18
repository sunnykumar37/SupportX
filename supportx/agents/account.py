
import json
from pathlib import Path

from ..logging_utils import ExecutionLogger
from ..models import TicketState


class AccountSpecialist:
    def __init__(self, logger: ExecutionLogger, records_path: Path):
        self.logger = logger
        self.records_path = records_path

    def check_account_status(self, customer_id: str) -> dict | None:
        records = json.loads(
            self.records_path.read_text(encoding="utf-8")
        )

        return next(
            (
                record for record in records
                if record.get("customer_id") == customer_id
            ),
            None
        )

    def validate_account_recovery_request(self, message: str) -> bool:
        sensitive_patterns = (
            "password is",
            "password:",
            "my password",
            "otp:",
            "otp is",
            "one-time code",
            "verification code",
            "security code",
        )

        message = message.lower()
        return not any(term in message for term in sensitive_patterns)

    def run(self, ticket: TicketState) -> TicketState:
        self.logger.event(
            "agent_activated", ticket, agent="account_specialist"
        )

        account = self.check_account_status(ticket.customer_id)
        valid = self.validate_account_recovery_request(
            ticket.original_message
        )

        ticket.tool_calls.extend([
            "check_account_status",
            "validate_account_recovery_request"
        ])

        if not valid:
            ticket.specialist_result = (
                "The request included sensitive credential material."
            )
            ticket.draft_response = (
                "For your security, please do not share passwords, "
                "one-time codes, or verification codes. "
                "I can guide you through secure account recovery."
            )

        elif account is None:
            ticket.specialist_result = (
                "No account record was found for this customer."
            )
            ticket.draft_response = (
                "I could not find an account associated with your "
                "customer ID. Please verify your details or contact support."
            )

        elif account.get("status", "").lower() == "locked":
            ticket.specialist_result = (
                "The account is locked according to the support record."
            )
            ticket.draft_response = (
                "Your account is currently marked as locked. "
                "Please contact human support for assistance with recovery."
            )

        elif not account.get("email_verified", False):
            ticket.specialist_result = (
                "The account email is not verified."
            )
            ticket.draft_response = (
                "Your account email is not verified. Please complete "
                "email verification through the official verification "
                "process before attempting account recovery."
            )

        elif account.get("status", "").lower() == "active":
            ticket.specialist_result = (
                "The account is active and its email is verified."
            )
            ticket.draft_response = (
                "Your account is active and your email is verified. "
                "If you cannot sign in, use the Forgot password option "
                "with your registered email. Never share your password "
                "or verification codes."
            )

        else:
            ticket.specialist_result = (
                f"The account has status: "
                f"{account.get('status', 'unknown')}."
            )
            ticket.draft_response = (
                "Your account requires further verification. "
                "Please contact human support for assistance."
            )

        self.logger.event(
            "specialist_response", ticket, specialist="account"
        )

        return ticket

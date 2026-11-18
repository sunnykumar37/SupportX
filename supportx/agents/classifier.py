
import re

from ..logging_utils import ExecutionLogger
from ..models import TicketState


class ClassifierAgent:
    LOW_CONFIDENCE_THRESHOLD = 0.65

    def __init__(self, logger: ExecutionLogger):
        self.logger = logger

    # Tool 1: Normalize customer ticket text
    def normalize_ticket_text(self, message: str) -> str:
        text = message.strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    # Tool 2: Classify the customer ticket
    def classify_ticket(self, message: str) -> tuple[str, float, str]:

        text = self.normalize_ticket_text(message)

        keyword_groups = {
            "Billing": [
                r"\bcharge(?:d)?\b",
                r"\binvoice\b",
                r"\bpayment\b",
                r"\brefund\b",
                r"\bbilling\b",
                r"\bprice\b",
                r"\bsubscription\b",
                r"\btransaction\b",
                r"\bdouble[- ]charged\b",
            ],

            "Technical": [
                r"\berror\b",
                r"\bfailure\b",
                r"\bfailed\b",
                r"\bbug\b",
                r"\bcrash(?:es|ed)?\b",
                r"\binstall(?:ation)?\b",
                r"\bblank screen\b",
                r"\bnot working\b",
                r"\bapplication crash\b",
                r"\btechnical\b",
                r"\bexception\b",
            ],

            "Account": [
                r"\blogin\b",
                r"\blog in\b",
                r"\bsign in\b",
                r"\bpassword\b",
                r"\baccess\b",
                r"\blocked\b",
                r"\baccount\b",
                r"\bforgot password\b",
            ],
        }

        scores = {}

        # Calculate category scores
        for category, patterns in keyword_groups.items():

            matches = sum(
                bool(re.search(pattern, text))
                for pattern in patterns
            )

            scores[category] = matches

        # Sort categories by their scores
        ranked = sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True
        )

        category, matches = ranked[0]

        # No matching keywords
        if matches == 0:
            return (
                "Other",
                0.25,
                "No category-specific terms were found."
            )

        # Handle ambiguous classification
        if ranked[1][1] == matches:
            return (
                "Other",
                0.35,
                "Multiple categories have equal matching scores."
            )

        # Calculate confidence
        confidence = min(
            0.95,
            0.58 + (matches - 1) * 0.12
        )

        explanation = (
            f"Matched {matches} {category.lower()} "
            f"support keyword(s)."
        )

        return category, confidence, explanation

    # Main agent execution
    def run(self, ticket: TicketState) -> TicketState:

        self.logger.event(
            "agent_activated",
            ticket,
            agent="classifier"
        )

        category, confidence, explanation = (
            self.classify_ticket(ticket.original_message)
        )

        assigned = {
            "Billing": "billing_specialist",
            "Technical": "technical_specialist",
            "Account": "account_specialist"
        }.get(category, "unassigned")

        ticket.update(
            detected_category=category,
            confidence_score=confidence,
            classification_explanation=explanation,
            assigned_specialist=assigned
        )

        ticket.tool_calls.extend([
            "normalize_ticket_text",
            "classify_ticket"
        ])

        self.logger.event(
            "classification_result",
            ticket,
            category=category,
            confidence=confidence,
            low_confidence=confidence < self.LOW_CONFIDENCE_THRESHOLD
        )

        return ticket

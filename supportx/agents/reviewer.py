
from ..logging_utils import ExecutionLogger
from ..models import TicketState


class ReviewerAgent:

    def __init__(self, logger: ExecutionLogger):
        self.logger = logger

    # Tool 1: Check professional tone
    def check_reply_tone(self, response: str) -> bool:

        if not response or not response.strip():
            return False

        inappropriate_words = (
            "idiot",
            "stupid",
            "whatever",
            "shut up",
            "not my problem"
        )

        text = response.lower()

        return not any(
            word in text for word in inappropriate_words
        )

    # Tool 2: Check response completeness
    def check_reply_completeness(
        self,
        response: str,
        ticket: TicketState
    ) -> bool:

        if not response or not response.strip():
            return False

        words = response.split()

        if len(words) < 8:
            return False

        if not ticket.detected_category:
            return False

        # Check for a meaningful next step
        action_phrases = (
            "please",
            "try",
            "check",
            "follow",
            "contact",
            "verify",
            "visit",
            "restart",
            "reset",
            "review"
        )

        text = response.lower()

        has_action = any(
            phrase in text for phrase in action_phrases
        )

        return has_action

    # Main reviewer execution
    def review(self, ticket: TicketState) -> TicketState:

        self.logger.event(
            "agent_activated",
            ticket,
            agent="reviewer"
        )

        response = ticket.draft_response or ""

        tone_ok = self.check_reply_tone(response)

        complete = self.check_reply_completeness(
            response, ticket
        )

        approved = tone_ok and complete

        feedback = []

        if not tone_ok:
            feedback.append(
                "Response must use professional and respectful language."
            )

        if not complete:
            feedback.append(
                "Response must contain sufficient detail and "
                "a clear actionable next step."
            )

        ticket.reviewer_status = (
            "approved" if approved else "revision_required"
        )

        ticket.reviewer_feedback = (
            "Approved for customer delivery."
            if approved
            else " ".join(feedback)
        )

        ticket.tool_calls.extend([
            "check_reply_tone",
            "check_reply_completeness"
        ])

        self.logger.event(
            "reviewer_decision",
            ticket,
            status=ticket.reviewer_status,
            tone_ok=tone_ok,
            completeness=complete,
            feedback=ticket.reviewer_feedback
        )

        return ticket

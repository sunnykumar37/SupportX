
import json
import os
import re
from pathlib import Path

from .agents.account import AccountSpecialist
from .agents.billing import BillingSpecialist
from .agents.classifier import ClassifierAgent
from .agents.escalation import EscalationRouter
from .agents.reviewer import ReviewerAgent
from .agents.technical import TechnicalSpecialist
from .config import DATA_DIR, STORAGE_DIR, settings
from .llm import LLMService
from .logging_utils import ExecutionLogger
from .memory import ConversationMemory
from .models import TicketState
from .rag import KnowledgeBase
from .storage import TicketRepository


class SupportXController:
    """
    Coordinates SupportX's multi-agent workflow.

    The deterministic classifier provides the initial classification.
    Groq proposes routing plans for sufficiently confident tickets.
    Existing specialist agents execute the actual operations.
    """

    VALID_CATEGORIES = {"Billing", "Technical", "Account", "Other"}

    def __init__(self, storage_dir: Path = STORAGE_DIR):
        storage_dir.mkdir(parents=True, exist_ok=True)

        self.logger = ExecutionLogger(storage_dir / "execution.jsonl")
        self.repository = TicketRepository(storage_dir / "tickets.json")
        self.memory = ConversationMemory(self.repository)

        self.classifier = ClassifierAgent(self.logger)

        self.billing = BillingSpecialist(
            self.logger,
            DATA_DIR / "billing_records.json"
        )

        self.technical = TechnicalSpecialist(
            self.logger,
            KnowledgeBase()
        )

        self.account = AccountSpecialist(
            self.logger,
            DATA_DIR / "accounts.json"
        )

        self.reviewer = ReviewerAgent(self.logger)
        self.escalation = EscalationRouter(self.logger, storage_dir)

        self.llm = LLMService()

        self.agentic_mode = (
            os.getenv("SUPPORTX_AGENTIC_MODE", "false").lower() == "true"
            and self.llm.mode == "groq"
        )

    def _extract_json(self, response: str) -> dict:
        """Extract a JSON object from the LLM response."""

        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                "The agentic planner did not return JSON."
            )

        result = json.loads(cleaned[start:end + 1])

        if not isinstance(result, dict):
            raise ValueError(
                "The agentic plan must be a JSON object."
            )

        return result

    def _create_agentic_plan(self, ticket: TicketState) -> dict:
        """Ask Groq to interpret the request and propose a routing plan."""

        prompt = f"""
You are the planning agent for SupportX, a multi-agent customer
support system.

Analyze the customer request and choose the most appropriate
specialist.

Available specialists:
1. Billing: invoices, duplicate charges, payments, refunds.
2. Technical: bugs, errors, application problems, troubleshooting.
3. Account: login, password reset, locked accounts, verification.
4. Other: requests that do not fit these categories.

Customer message:
{ticket.original_message}

Previous customer context:
{ticket.previous_context}

Return ONLY a valid JSON object in this exact format:

{{
    "category": "Billing",
    "reason": "Short explanation for the routing decision",
    "next_action": "Run the billing specialist"
}}

Rules:
- category must be Billing, Technical, Account, or Other.
- Never invent customer information or transaction details.
- Do not claim that an operation has already been completed.
- Choose the specialist based on the actual customer request.
"""

        response = self.llm.generate(prompt)
        plan = self._extract_json(response)

        category = plan.get("category")

        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                "The planner returned an invalid category."
            )

        return {
            "category": category,
            "reason": str(plan.get("reason", "")),
            "next_action": str(plan.get("next_action", "")),
        }

    def _select_specialist(self, ticket: TicketState) -> None:
        """
        Use Groq planning only when the initial classification
        meets the minimum confidence threshold.
        """

        threshold = self.classifier.LOW_CONFIDENCE_THRESHOLD

        # SAFEGUARD 1: Block Groq from overriding uncertain classifications.
        if ticket.confidence_score < threshold:
            ticket.update(
                detected_category="Other",
                assigned_specialist="unassigned"
            )

            self.logger.event(
                "agentic_planning_skipped",
                ticket,
                reason="Initial classification confidence is below threshold.",
                confidence=ticket.confidence_score,
                threshold=threshold
            )
            return

        if not self.agentic_mode:
            self.logger.event(
                "agentic_planning_skipped",
                ticket,
                reason="Agentic mode is disabled or Groq is unavailable.",
                selected_category=ticket.detected_category
            )
            return

        try:
            plan = self._create_agentic_plan(ticket)

            ticket.update(
                detected_category=plan["category"],
                assigned_specialist={
                    "Billing": "billing_specialist",
                    "Technical": "technical_specialist",
                    "Account": "account_specialist"
                }.get(plan["category"], "unassigned")
            )

            self.logger.event(
                "agentic_plan_created",
                ticket,
                selected_category=plan["category"],
                reason=plan["reason"],
                next_action=plan["next_action"]
            )

        except Exception as exc:
            # Retain the original classifier decision if Groq fails.
            self.logger.event(
                "agentic_planning_failed",
                ticket,
                error=str(exc),
                fallback_category=ticket.detected_category
            )

    def _execute_specialist(self, ticket: TicketState) -> None:
        """Execute the selected specialist after confidence validation."""

        threshold = self.classifier.LOW_CONFIDENCE_THRESHOLD

        # SAFEGUARD 2: Never execute a specialist for an uncertain ticket.
        if ticket.confidence_score < threshold:
            ticket.update(
                detected_category="Other",
                assigned_specialist="unassigned"
            )

            ticket.specialist_result = (
                "The request could not be confidently classified."
            )

            ticket.draft_response = (
                "I need a little more detail to understand your issue. "
                "Your request will be reviewed by human support."
            )

            self.logger.event(
                "low_confidence_routing_blocked",
                ticket,
                confidence=ticket.confidence_score,
                threshold=threshold
            )
            return

        self.logger.event(
            "specialist_routing",
            ticket,
            selected_category=ticket.detected_category
        )

        if ticket.detected_category == "Billing":
            self.billing.run(ticket)

        elif ticket.detected_category == "Technical":
            self.technical.run(ticket)

        elif ticket.detected_category == "Account":
            self.account.run(ticket)

        else:
            ticket.specialist_result = (
                "The request could not be assigned to a specialist."
            )

            ticket.draft_response = (
                "I need a little more detail to route this request "
                "to the right support specialist."
            )

    def _revise_response(self, ticket: TicketState) -> None:
        ticket.revision_attempts += 1

        ticket.draft_response = (
            f"{ticket.draft_response.rstrip('.')} "
            "Please follow the verified next step above, and contact "
            "human support if it does not resolve the issue."
        )

    def process(self, customer_id: str, message: str) -> TicketState:
        if not customer_id.strip() or not message.strip():
            raise ValueError(
                "Customer ID and message are required."
            )

        ticket = TicketState.new(
            customer_id.strip(),
            message.strip()
        )

        self.logger.event("ticket_received", ticket)

        # Retrieve previous customer interactions.
        ticket.previous_context = self.memory.retrieve(
            ticket.customer_id
        )

        # Step 1: Initial classification.
        self.classifier.run(ticket)

        # Step 2: Groq proposes routing when confidence permits.
        self._select_specialist(ticket)

        # Step 3: Execute the selected specialist.
        self._execute_specialist(ticket)

        # Step 4: Reviewer validates the response.
        while ticket.revision_attempts < settings.max_revision_attempts:
            self.reviewer.review(ticket)

            if ticket.reviewer_status == "approved":
                break

            self._revise_response(ticket)

        # Step 5: Escalate unresolved or low-confidence requests.
        self.escalation.run(ticket)

        # Step 6: Prepare final response.
        if (
            ticket.reviewer_status == "approved"
            and ticket.escalation_status == "not_required"
        ):
            ticket.final_response = ticket.draft_response

        else:
            ticket.final_response = (
                ticket.draft_response
                if ticket.reviewer_status == "approved"
                else "Your request has been sent to human support for review."
            )

        self.logger.event(
            "final_response",
            ticket,
            response=ticket.final_response
        )

        # Step 7: Save interaction to customer memory.
        self.memory.remember(ticket)

        return ticket

    def dashboard(self) -> dict:
        tickets = self.repository.all()

        return {
            "total": len(tickets),

            "billing": sum(
                t.detected_category == "Billing"
                for t in tickets
            ),

            "technical": sum(
                t.detected_category == "Technical"
                for t in tickets
            ),

            "account": sum(
                t.detected_category == "Account"
                for t in tickets
            ),

            "resolved": sum(
                t.escalation_status == "not_required"
                and bool(t.final_response)
                for t in tickets
            ),

            "escalated": sum(
                t.escalation_status == "escalated"
                for t in tickets
            ),

            "recent": [
                ticket.to_dict()
                for ticket in tickets[-10:]
            ],
        }

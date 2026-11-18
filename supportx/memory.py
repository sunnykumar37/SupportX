from .models import TicketState
from .storage import TicketRepository


class ConversationMemory:
    def __init__(self, repository: TicketRepository):
        self.repository = repository

    def retrieve(self, customer_id: str, limit: int = 3) -> list[dict]:
        tickets = self.repository.find_customer(customer_id)
        return [
            {"ticket_id": ticket.ticket_id, "message": ticket.original_message, "response": ticket.final_response, "category": ticket.detected_category}
            for ticket in tickets[-limit:]
        ]

    def remember(self, ticket: TicketState) -> None:
        self.repository.save(ticket)
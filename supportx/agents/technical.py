
from ..config import settings
from ..logging_utils import ExecutionLogger
from ..models import TicketState
from ..rag import KnowledgeBase, TechnicalTools


class TechnicalSpecialist:
    def __init__(
        self,
        logger: ExecutionLogger,
        knowledge_base: KnowledgeBase
    ):
        self.logger = logger
        self.tools = TechnicalTools(knowledge_base)

    def run(self, ticket: TicketState) -> TicketState:
        self.logger.event(
            "agent_activated",
            ticket,
            agent="technical_specialist"
        )

        # Retrieve relevant knowledge
        passages = self.tools.retrieve_knowledge(
            ticket.original_message
        )

        # Normalize source names and save retrieved knowledge
        ticket.retrieved_knowledge = [
            {
                "source": (
                    item.source
                    if isinstance(item.source, str)
                    else str(item.source)
                ),
                "text": item.text,
                "score": round(item.score, 3)
            }
            for item in passages
        ]

        threshold = settings.retrieval_threshold

        relevant_passages = [
            item for item in passages
            if item.score >= threshold
        ]

        # Check whether sufficient knowledge was retrieved
        grounded = self.tools.run_troubleshooting_check(
            ticket.original_message,
            passages
        )

        ticket.tool_calls.extend([
            "retrieve_knowledge",
            "run_troubleshooting_check"
        ])

        if grounded and relevant_passages:

            context = " ".join(
                item.text for item in relevant_passages
            )

            # Convert source values into hashable strings
            sources = sorted({
                str(item.source)
                for item in relevant_passages
            })

            ticket.specialist_result = (
                f"Grounded guidance: {context} "
                f"Sources: {', '.join(sources)}"
            )

            ticket.draft_response = (
                f"I found relevant support guidance: {context} "
                "Please follow these steps and let us know if "
                "the issue continues."
            )

        else:
            ticket.specialist_result = (
                "There is not enough relevant information in the "
                "knowledge base to resolve this issue confidently."
            )

            ticket.draft_response = (
                "I could not find enough verified technical information "
                "to resolve this confidently. A human specialist should "
                "investigate further."
            )

        # Log retrieval results
        self.logger.event(
            "rag_retrieval_result",
            ticket,
            sources=[
                str(item.source)
                for item in relevant_passages
            ],
            grounded=grounded
        )

        self.logger.event(
            "specialist_response",
            ticket,
            specialist="technical"
        )

        return ticket

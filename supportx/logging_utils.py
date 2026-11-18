import json
from pathlib import Path
from typing import Any

from .models import TicketState, utc_now


class ExecutionLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event: str, ticket: TicketState | None = None, **details: Any) -> None:
        record = {"timestamp": utc_now(), "event": event, **details}
        if ticket:
            record["ticket_id"] = ticket.ticket_id
            ticket.execution_trace.append(event)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
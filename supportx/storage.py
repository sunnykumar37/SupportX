import json
from pathlib import Path
from typing import Any

from .models import TicketState, state_from_dict


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def read(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON in {self.path}") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"Expected a list in {self.path}")
        return data

    def append(self, value: dict[str, Any]) -> None:
        values = self.read()
        values.append(value)
        self.path.write_text(json.dumps(values, indent=2), encoding="utf-8")

    def replace_by_id(self, field: str, identifier: str, value: dict[str, Any]) -> None:
        values = self.read()
        for index, existing in enumerate(values):
            if existing.get(field) == identifier:
                values[index] = value
                self.path.write_text(json.dumps(values, indent=2), encoding="utf-8")
                return
        self.append(value)


class TicketRepository:
    def __init__(self, path: Path):
        self.store = JsonStore(path)

    def save(self, ticket: TicketState) -> None:
        self.store.replace_by_id("ticket_id", ticket.ticket_id, ticket.to_dict())

    def all(self) -> list[TicketState]:
        return [state_from_dict(item) for item in self.store.read()]

    def find_customer(self, customer_id: str) -> list[TicketState]:
        return [ticket for ticket in self.all() if ticket.customer_id == customer_id]
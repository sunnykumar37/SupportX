
from groq import Groq

from .config import settings


class LLMService:
    """Groq-backed LLM service with deterministic demo fallback."""

    def __init__(self):
        self.mode = (
            "demo"
            if settings.demo_mode or not settings.groq_api_key
            else "groq"
        )

        self.client = (
            Groq(api_key=settings.groq_api_key)
            if self.mode == "groq"
            else None
        )

    def generate(self, prompt: str) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if self.mode == "demo":
            return (
                "Deterministic demo mode is active; "
                "specialist tools supplied the response."
            )

        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are SupportX, an enterprise customer "
                            "support AI assistant. Give clear, accurate "
                            "and helpful responses. Never invent customer "
                            "records, payment details or account status."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=800
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError("Groq returned an empty response.")

            return content.strip()

        except Exception as exc:
            raise RuntimeError(
                f"Groq request failed: {exc}"
            ) from exc

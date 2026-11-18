from .config import settings


class LLMService:
    """Optional Groq-backed service; demo mode remains deterministic and explicit."""

    def __init__(self):
        self.mode = "demo" if settings.demo_mode or not settings.groq_api_key else "groq"

    def generate(self, prompt: str) -> str:
        if self.mode == "demo":
            return "Deterministic demo mode is active; specialist tools supplied the response."
        try:
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
            service = OpenAIChatCompletion(ai_model_id=settings.groq_model, api_key=settings.groq_api_key, endpoint="https://api.groq.com/openai/v1")
            return str(service)
        except (ImportError, RuntimeError) as exc:
            raise RuntimeError("Groq integration is configured but Semantic Kernel is unavailable.") from exc